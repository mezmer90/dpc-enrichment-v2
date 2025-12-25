"""
Enrichment Orchestrator

Coordinates the entire enrichment pipeline:
1. Load practice data
2. Create async worker pool
3. For each practice:
   - Scrape website (with fallbacks)
   - Convert to markdown (with fallbacks)
   - Merge pages
   - Save markdown
   - Extract fields with AI
   - Save enriched data
4. Track progress and statistics
5. Handle errors gracefully
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

from .config import (
    MAX_PAGES_PER_PRACTICE,
    IMPORTANT_PAGES,
    SCRAPER_TIMEOUT,
    MAX_WORKERS,
    CHECKPOINT_INTERVAL
)
from .scraper.scraper_factory import ScraperFactory
from .scraper.base_scraper import ScraperStatus, ScraperResult, ScraperMethod
from .scraper.circuit_breaker import CircuitBreakerManager, CircuitBreakerOpenError, CircuitState
from .markdown.converter import MarkdownConverter
from .markdown.merger import MarkdownMerger
from .ai.gemini_client import GeminiClient
from .ai.extractor import FieldExtractor
from .storage.markdown_storage import MarkdownStorage
from .storage.data_storage import DataStorage
from .utils.progress import ProgressTracker, PracticeStatus
from .utils.rate_limiter import RateLimiter
from .utils.api_exceptions import APIBudgetError, APIRateLimitError
from .utils.api_pause_handler import APIPauseHandler

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentStats:
    """Statistics for enrichment run"""
    total_practices: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0

    total_pages_scraped: int = 0
    total_markdown_chars: int = 0
    total_cost: float = 0.0
    total_time: float = 0.0

    scraper_usage: Dict[str, int] = field(default_factory=dict)
    failure_reasons: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert stats to dict"""
        return {
            'total_practices': self.total_practices,
            'successful': self.successful,
            'failed': self.failed,
            'skipped': self.skipped,
            'success_rate': f"{(self.successful / max(1, self.total_practices)) * 100:.1f}%",
            'total_pages_scraped': self.total_pages_scraped,
            'total_markdown_chars': self.total_markdown_chars,
            'total_cost': f"${self.total_cost:.2f}",
            'total_time': f"{self.total_time:.1f}s",
            'avg_time_per_practice': f"{self.total_time / max(1, self.total_practices):.1f}s",
            'scraper_usage': self.scraper_usage,
            'failure_reasons': self.failure_reasons,
        }


class EnrichmentOrchestrator:
    """
    Orchestrates the entire enrichment pipeline.

    Manages:
    - Async worker pool
    - Scraping with fallbacks
    - Markdown processing
    - AI extraction
    - Progress tracking
    - Error handling
    - Statistics collection
    """

    def __init__(
        self,
        openrouter_api_key: str,
        input_file: Path,
        output_file: Path,
        markdown_dir: Path,
        progress_file: Path,
        max_workers: int = MAX_WORKERS,
        checkpoint_interval: int = CHECKPOINT_INTERVAL,
        use_pooled_first: bool = False,
        resume: bool = False,
        limit: Optional[int] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            openrouter_api_key: OpenRouter API key for Gemini
            input_file: Input JSON file with practice data
            output_file: Output JSON file for enriched data
            markdown_dir: Directory for markdown storage
            progress_file: Progress tracking file
            max_workers: Max concurrent workers
            checkpoint_interval: Save progress every N practices
            use_pooled_first: Process pooled practices first
            resume: Resume from previous run
            limit: Limit number of practices to process (for testing)
        """
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.markdown_dir = Path(markdown_dir)
        self.progress_file = Path(progress_file)
        self.max_workers = max_workers
        self.checkpoint_interval = checkpoint_interval
        self.use_pooled_first = use_pooled_first
        self.resume = resume
        self.limit = limit

        # Initialize components
        self.gemini_client = GeminiClient(api_key=openrouter_api_key)
        self.extractor = FieldExtractor(gemini_client=self.gemini_client)
        self.markdown_storage = MarkdownStorage(base_dir=markdown_dir)
        self.progress_tracker = ProgressTracker(
            state_file=progress_file,
            checkpoint_interval=checkpoint_interval
        )
        self.rate_limiter = RateLimiter()
        self.circuit_breaker_manager = CircuitBreakerManager()
        self.api_pause_handler = APIPauseHandler()

        # Statistics
        self.stats = EnrichmentStats()
        self._stats_lock = asyncio.Lock()

        # Enriched data storage
        self._enriched_practices: List[Dict] = []
        self._enriched_lock = asyncio.Lock()

        # Progress tracking
        self._current_count = 0
        self._count_lock = asyncio.Lock()

        # Incremental save counter
        self._save_count = 0
        self._save_lock = asyncio.Lock()

        # Worker pool
        self._thread_pool: Optional[ThreadPoolExecutor] = None

        logger.info(f"Orchestrator initialized: {max_workers} workers, resume={resume}")

    async def run(self):
        """
        Run the complete enrichment pipeline.

        Returns:
            Final statistics dict
        """
        start_time = datetime.now()

        try:
            # Load practice data
            practices = await self._load_practices()
            self.stats.total_practices = len(practices)

            logger.info(f"Starting enrichment: {len(practices)} practices")

            # Initialize thread pool for blocking operations
            self._thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)

            # Create async worker pool
            semaphore = asyncio.Semaphore(self.max_workers)
            tasks = []

            for practice in practices:
                task = asyncio.create_task(
                    self._enrich_practice_with_semaphore(practice, semaphore)
                )
                tasks.append(task)

            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            # Save final results
            await self._save_final_results()

            # Calculate total time
            self.stats.total_time = (datetime.now() - start_time).total_seconds()

            # Log final statistics
            self._log_final_stats()

            return self.stats.to_dict()

        finally:
            # Cleanup
            if self._thread_pool:
                self._thread_pool.shutdown(wait=True)

            # Save final progress
            self.progress_tracker.save()

            # Save enriched data if interrupted (with timeout to prevent deadlock)
            try:
                # Use timeout to prevent infinite wait if lock is held by cancelled task
                async def save_with_timeout():
                    async with self._enriched_lock:
                        if self._enriched_practices:
                            logger.info("Saving enriched data before exit...")
                            await self._save_incremental_results()

                # Wait max 10 seconds for save to complete
                await asyncio.wait_for(save_with_timeout(), timeout=10.0)

            except asyncio.TimeoutError:
                logger.warning(
                    "Save on exit timed out after 10 seconds (lock may be held by cancelled task). "
                    "Data was saved during last checkpoint. Exiting now."
                )
            except Exception as e:
                logger.error(f"Failed to save enriched data on exit: {e}")

    async def _enrich_practice_with_semaphore(
        self,
        practice: Dict,
        semaphore: asyncio.Semaphore
    ):
        """
        Enrich a single practice with semaphore for concurrency control.

        Args:
            practice: Practice data dict
            semaphore: Semaphore for limiting concurrent workers
        """
        async with semaphore:
            await self._enrich_practice(practice)

    async def _enrich_practice(self, practice: Dict):
        """
        Enrich a single practice through complete pipeline.

        Args:
            practice: Practice data dict
        """
        practice_id = practice['practice_id']
        practice_name = practice.get('practice_name', practice_id)
        website_url = practice.get('website_url', '')

        # Sanitize practice name for console display (Windows console encoding)
        display_name = practice_name.encode('ascii', errors='replace').decode('ascii')

        # Increment progress counter
        async with self._count_lock:
            self._current_count += 1
            current_num = self._current_count

        try:
            logger.info(f"Processing {current_num}/{self.stats.total_practices}: {display_name}")

            # Check if website URL exists and is valid
            if not website_url or website_url == '-NA-':
                logger.warning(f"[{practice_id}] No website URL, skipping")
                await self._update_stats(skipped=1, failure_reason='no_website')
                self.progress_tracker.update_status(
                    practice_id,
                    PracticeStatus.SKIPPED,
                    error='No website URL'
                )
                return

            # Skip invalid/placeholder URLs (na, n/a, none, etc.)
            url_lower = website_url.lower().strip()
            invalid_patterns = ['://na/', '://na', '/na/', 'n/a', 'none', 'null', 'undefined', '://www.na']
            if any(pattern in url_lower for pattern in invalid_patterns) or url_lower in ['na', 'n/a']:
                logger.warning(f"[{practice_id}] Invalid placeholder URL: {website_url}, skipping")
                await self._update_stats(skipped=1, failure_reason='invalid_url')
                self.progress_tracker.update_status(
                    practice_id,
                    PracticeStatus.SKIPPED,
                    error=f'Invalid placeholder URL: {website_url}'
                )
                return

            # Check circuit breaker for domain
            domain = self._extract_domain(website_url)
            breaker = self.circuit_breaker_manager.get_breaker(domain)

            if breaker.state == CircuitState.OPEN:
                logger.warning(f"[{practice_id}] Circuit breaker open for {domain}, skipping")
                await self._update_stats(skipped=1, failure_reason='circuit_breaker_open')
                self.progress_tracker.update_status(
                    practice_id,
                    PracticeStatus.SKIPPED,
                    error=f'Circuit breaker open for {domain}'
                )
                return

            # Step 1: Scrape website
            scraper_result = await self._scrape_with_fallbacks(
                website_url,
                practice_id,
                breaker
            )

            if scraper_result.status != ScraperStatus.SUCCESS:
                logger.error(f"[{practice_id}] Scraping failed: {scraper_result.error_message}")
                await self._update_stats(failed=1, failure_reason=f'scraping_{scraper_result.status.value}')
                self.progress_tracker.update_status(
                    practice_id,
                    PracticeStatus.FAILED,
                    error=scraper_result.error_message,
                    scraper_method=scraper_result.method.value
                )
                return

            # Log scraping success
            logger.info(f"  Scraped: {scraper_result.pages_crawled} pages ({len(scraper_result.get_merged_markdown())} chars)")

            # Step 2: Merge markdown pages
            merged_markdown = scraper_result.get_merged_markdown()

            if not merged_markdown or len(merged_markdown) < 100:
                logger.error(f"[{practice_id}] Insufficient markdown content: {len(merged_markdown)} chars")
                await self._update_stats(failed=1, failure_reason='insufficient_content')
                self.progress_tracker.update_status(
                    practice_id,
                    PracticeStatus.FAILED,
                    error='Insufficient markdown content'
                )
                return

            # Step 3: Save markdown files
            self.markdown_storage.save_scraper_result(
                practice_id=practice_id,
                result=scraper_result,
                merged_markdown=merged_markdown
            )

            # Step 4: Extract fields with AI
            extracted = await self.extractor.extract(
                markdown=merged_markdown,
                practice_data=practice
            )

            # Count non-null extracted fields (excluding metadata)
            field_count = sum(1 for k, v in extracted.items()
                            if not k.startswith('_') and v not in (None, '', [], {}))
            cost = extracted.get('_enrichment_metadata', {}).get('llm_cost', 0)
            logger.info(f"  Enriched: {field_count} fields extracted (cost: ${cost:.4f})")

            # Step 5: Build final enriched practice
            enriched_practice = self._build_enriched_practice(
                practice,
                extracted,
                scraper_result
            )

            # Store enriched data
            async with self._enriched_lock:
                self._enriched_practices.append(enriched_practice)

            # Update progress (with metadata for tracking)
            self.progress_tracker.update_status(
                practice_id,
                PracticeStatus.SUCCESS,
                scraper_method=scraper_result.method.value,
                pages_crawled=scraper_result.pages_crawled,
                ai_cost=extracted.get('_enrichment_metadata', {}).get('llm_cost', 0)
            )

            # Incremental save: Save enriched data every checkpoint_interval practices
            async with self._save_lock:
                self._save_count += 1
                if self._save_count % self.checkpoint_interval == 0:
                    await self._save_incremental_results()
                    # Log every 10 saves to avoid spam (even though we save every practice)
                    if self._save_count % 10 == 0:
                        logger.info(f"Progress saved: {self._save_count} practices persisted to disk")
                    else:
                        logger.debug(f"Auto-saved practice {self._save_count}")

            # Update statistics
            await self._update_stats(
                successful=1,
                pages_scraped=scraper_result.pages_crawled,
                markdown_chars=scraper_result.total_markdown_chars,
                cost=extracted.get('_enrichment_metadata', {}).get('llm_cost', 0),
                scraper_method=scraper_result.method.value
            )

            logger.info(f"  [SUCCESS] {display_name} completed!")

        except (APIBudgetError, APIRateLimitError) as e:
            # API budget/rate limit error - PAUSE enrichment, don't mark as failed
            logger.error(f"[{practice_id}] API issue detected: {e}")

            # Determine error type
            error_type = 'budget' if isinstance(e, APIBudgetError) else 'rate_limit'
            retry_after = getattr(e, 'retry_after', None)

            # Pause the enrichment
            self.api_pause_handler.pause_for_api_issue(
                api_name=e.api_name,
                error_type=error_type,
                error_message=e.message,
                retry_after=retry_after
            )

            # Prompt user to resume
            should_resume = self.api_pause_handler.prompt_user_to_resume()

            if should_resume:
                # Test API connection before resuming
                logger.info(f"Testing {e.api_name} connection...")

                # Resume enrichment
                self.api_pause_handler.resume()

                # Re-raise the exception to retry this practice
                # The orchestrator will continue from this practice
                logger.info(f"Retrying practice: {practice_id}")
                raise

            else:
                # User chose to stop - raise to halt enrichment
                raise KeyboardInterrupt("User stopped enrichment due to API issue")

        except CircuitBreakerOpenError:
            logger.warning(f"[{practice_id}] Circuit breaker triggered")
            await self._update_stats(skipped=1, failure_reason='circuit_breaker')
            self.progress_tracker.update_status(
                practice_id,
                PracticeStatus.SKIPPED,
                error='Circuit breaker open'
            )

        except Exception as e:
            logger.error(f"[{practice_id}] Enrichment failed: {e}", exc_info=True)
            await self._update_stats(failed=1, failure_reason=f'error_{type(e).__name__}')
            self.progress_tracker.update_status(
                practice_id,
                PracticeStatus.FAILED,
                error=str(e)
            )

    async def _scrape_with_fallbacks(
        self,
        url: str,
        practice_id: str,
        breaker
    ) -> ScraperResult:
        """
        Scrape website with fallback chain.

        Args:
            url: Website URL
            practice_id: Practice identifier
            breaker: Circuit breaker for domain

        Returns:
            ScraperResult from successful scraper
        """
        # Create scrapers in priority order
        scrapers = ScraperFactory.create_with_fallback(
            timeout=SCRAPER_TIMEOUT
        )

        for scraper in scrapers:
            try:
                logger.debug(f"[{practice_id}] Trying {scraper.__class__.__name__}")

                # Execute with circuit breaker protection
                result = await breaker.call_async(
                    scraper.scrape_multi_page,
                    base_url=url,
                    max_pages=MAX_PAGES_PER_PRACTICE,
                    important_paths=IMPORTANT_PAGES
                )

                if result.status == ScraperStatus.SUCCESS:
                    logger.debug(
                        f"[{practice_id}] SUCCESS: {scraper.__class__.__name__} succeeded: "
                        f"{result.pages_crawled} pages"
                    )
                    return result
                else:
                    logger.debug(
                        f"[{practice_id}] {scraper.__class__.__name__} failed: "
                        f"{result.error_message}"
                    )

            except Exception as e:
                logger.debug(
                    f"[{practice_id}] {scraper.__class__.__name__} error: {e}"
                )
                continue

        # All scrapers failed
        return ScraperResult(
            status=ScraperStatus.ERROR,
            method=scrapers[-1].get_method() if scrapers else ScraperMethod.CRAWL4AI,
            pages=[],
            error_message="All scrapers failed"
        )

    def _build_enriched_practice(
        self,
        original: Dict,
        extracted: Dict,
        scraper_result: ScraperResult
    ) -> Dict:
        """
        Build final enriched practice by merging original and extracted data.

        Args:
            original: Original practice data from DPC Frontier
            extracted: Extracted data from AI
            scraper_result: Scraping result metadata

        Returns:
            Complete enriched practice dict
        """
        # Start with original data
        enriched = original.copy()

        # Add extracted fields (don't overwrite original with -NA-)
        for key, value in extracted.items():
            if key.startswith('_'):
                # Metadata fields
                enriched[key] = value
            elif value != '-NA-' and value != -1:
                # Only update if we got real data
                enriched[key] = value
            elif key not in enriched:
                # Add field even if -NA- (for schema completeness)
                enriched[key] = value

        # Add enrichment metadata
        enriched['enrichment_status'] = 'completed'
        enriched['enriched_at'] = datetime.now().isoformat()
        enriched['enrichment_version'] = '2.0'

        # Add scraper metadata
        if '_scraper_metadata' not in enriched:
            enriched['_scraper_metadata'] = {}

        enriched['_scraper_metadata'].update({
            'scraper_method': scraper_result.method.value,
            'pages_crawled': scraper_result.pages_crawled,
            'total_markdown_chars': scraper_result.total_markdown_chars,
            'scrape_time': scraper_result.total_time,
            'bytes_downloaded': scraper_result.bytes_downloaded,
        })

        return enriched

    async def _load_practices(self) -> List[Dict]:
        """
        Load practices to enrich.

        Returns:
            List of practice dicts to process
        """
        # Load from input file (raw practice data)
        practices, metadata = DataStorage.load_enriched(self.input_file)
        logger.info(f"Loaded {len(practices)} practices from {self.input_file.name}")

        # Try to load previously enriched practices from output file (if exists)
        # This preserves work from previous runs
        previously_enriched = []
        if self.output_file.exists():
            try:
                previously_enriched, _ = DataStorage.load_enriched(self.output_file)
                logger.info(f"Found {len(previously_enriched)} previously enriched practices in output file")
            except Exception as e:
                logger.warning(f"Could not load previous enriched data: {e}")

        # Determine which practices to process based on progress tracker
        progress_file_exists = self.progress_file.exists()

        if progress_file_exists:
            # Load progress tracker
            self.progress_tracker.load()

            # Get practice statuses
            pending_ids = self.progress_tracker.get_pending()
            failed_ids = self.progress_tracker.get_failed()
            successful_ids = self.progress_tracker.get_successful()

            # Only resume if we actually have some progress (not just initialized)
            if successful_ids or failed_ids:
                logger.info(
                    f"[RESUME] Auto-resume detected: {len(successful_ids)} successful, "
                    f"{len(failed_ids)} failed, {len(pending_ids)} pending"
                )

                # Keep only successfully enriched practices (exclude failed ones for retry)
                to_retry_ids = set(failed_ids)
                kept_enriched = [
                    p for p in previously_enriched
                    if p['practice_id'] not in to_retry_ids
                ]

                async with self._enriched_lock:
                    self._enriched_practices = kept_enriched

                logger.info(
                    f"Kept {len(kept_enriched)} successful practices, "
                    f"will retry {len(to_retry_ids)} failed practices"
                )

                # Process pending + failed practices
                to_process_ids = set(pending_ids + failed_ids)
                practices = [p for p in practices if p['practice_id'] in to_process_ids]

                logger.info(f"Processing {len(practices)} remaining practices")
            else:
                # Progress file exists but empty (no completed/failed yet) - treat as fresh
                logger.info("Progress file exists but no progress yet, treating as fresh run")
                practice_ids = [p['practice_id'] for p in practices]
                self.progress_tracker.initialize_practices(practice_ids)
        else:
            # Fresh run - initialize progress tracker
            logger.info("Starting fresh run (no previous progress detected)")
            practice_ids = [p['practice_id'] for p in practices]
            self.progress_tracker.initialize_practices(practice_ids)

        # Sort by priority if using pooled first
        if self.use_pooled_first:
            practices.sort(
                key=lambda p: (
                    0 if p.get('pool_id') else 1,  # Pooled practices first
                    p.get('practice_name', '')
                )
            )
            logger.info("Processing pooled practices first")

        # Apply limit if specified (for testing)
        if self.limit and self.limit < len(practices):
            practices = practices[:self.limit]
            logger.info(f"[!] LIMIT APPLIED: Processing only {self.limit} practices (test mode)")

        return practices

    async def _save_incremental_results(self):
        """
        Save enriched results incrementally to prevent data loss.
        Called every checkpoint_interval practices.
        """
        try:
            # Get current enriched practices
            async with self._enriched_lock:
                completed = self._enriched_practices.copy()

            if not completed:
                return

            # Build metadata
            metadata = {
                'version': '2.0',
                'source': 'DPC Enrichment System V2 (Incremental Save)',
                'generated_at': datetime.now().isoformat(),
                'total_practices': len(completed),
                'statistics': self.stats.to_dict(),
                'note': 'This is an incremental save. Final file will be generated at completion.'
            }

            # Save enriched data (overwrites previous incremental save)
            DataStorage.save_enriched(
                practices=completed,
                output_file=self.output_file,
                metadata=metadata,
                create_backup=False  # Don't create backup for incremental saves
            )

            logger.debug(f"Incremental save complete: {len(completed)} practices")

        except Exception as e:
            logger.error(f"Incremental save failed (non-fatal): {e}")
            # Don't raise - incremental save failure shouldn't stop the process

    async def _save_final_results(self):
        """Save final enriched results to JSON file"""
        try:
            # Get enriched practices
            async with self._enriched_lock:
                completed = self._enriched_practices.copy()

            if not completed:
                logger.warning("No practices were successfully enriched")
                return

            # Build metadata
            metadata = {
                'version': '2.0',
                'source': 'DPC Enrichment System V2',
                'generated_at': datetime.now().isoformat(),
                'total_practices': len(completed),
                'statistics': self.stats.to_dict(),
            }

            # Save enriched data
            DataStorage.save_enriched(
                practices=completed,
                output_file=self.output_file,
                metadata=metadata,
                create_backup=True
            )

            logger.info(f"Saved {len(completed)} enriched practices to {self.output_file.name}")

        except Exception as e:
            logger.error(f"Failed to save final results: {e}")
            raise

    async def _update_stats(
        self,
        successful: int = 0,
        failed: int = 0,
        skipped: int = 0,
        pages_scraped: int = 0,
        markdown_chars: int = 0,
        cost: float = 0.0,
        scraper_method: str = '',
        failure_reason: str = ''
    ):
        """Update statistics (thread-safe)"""
        async with self._stats_lock:
            self.stats.successful += successful
            self.stats.failed += failed
            self.stats.skipped += skipped
            self.stats.total_pages_scraped += pages_scraped
            self.stats.total_markdown_chars += markdown_chars
            self.stats.total_cost += cost

            if scraper_method:
                self.stats.scraper_usage[scraper_method] = \
                    self.stats.scraper_usage.get(scraper_method, 0) + 1

            if failure_reason:
                self.stats.failure_reasons[failure_reason] = \
                    self.stats.failure_reasons.get(failure_reason, 0) + 1

    def _log_final_stats(self):
        """Log final statistics"""
        stats_dict = self.stats.to_dict()

        logger.info("=" * 80)
        logger.info("ENRICHMENT COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Total Practices: {stats_dict['total_practices']}")
        logger.info(f"Successful: {stats_dict['successful']}")
        logger.info(f"Failed: {stats_dict['failed']}")
        logger.info(f"Skipped: {stats_dict['skipped']}")
        logger.info(f"Success Rate: {stats_dict['success_rate']}")
        logger.info(f"Total Pages Scraped: {stats_dict['total_pages_scraped']}")
        logger.info(f"Total Markdown: {stats_dict['total_markdown_chars']:,} chars")
        logger.info(f"Total Cost: {stats_dict['total_cost']}")
        logger.info(f"Total Time: {stats_dict['total_time']}")
        logger.info(f"Avg Time/Practice: {stats_dict['avg_time_per_practice']}")
        logger.info("")
        logger.info("Scraper Usage:")
        for method, count in stats_dict['scraper_usage'].items():
            logger.info(f"  {method}: {count}")
        logger.info("")
        logger.info("Failure Reasons:")
        for reason, count in stats_dict['failure_reasons'].items():
            logger.info(f"  {reason}: {count}")
        logger.info("=" * 80)

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]
