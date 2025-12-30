"""
Enrichment Celery Task

Background task for enriching DPC practices with database integration.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from celery import Task
from sqlalchemy.orm import Session

from . import celery_app
from webapp.extensions import db
from webapp.models import Practice, EnrichmentRun, APIStatus
from webapp.services.progress_service import (
    publish_progress,
    ProgressEvent,
    update_stats_cache,
    get_run_control,
    clear_run_control
)
from src.enrichment_v2.orchestrator import EnrichmentOrchestrator
from src.enrichment_v2.config import (
    OPENROUTER_API_KEY,
    SCRAPERAPI_KEY,
    MAX_WORKERS,
    CHECKPOINT_INTERVAL
)

logger = logging.getLogger(__name__)


class EnrichmentTask(Task):
    """Custom Celery task with database session management"""

    def after_return(self, *args, **kwargs):
        """Clean up after task completion"""
        if hasattr(self, '_db_session'):
            self._db_session.close()


@celery_app.task(
    bind=True,
    base=EnrichmentTask,
    name='webapp.tasks.enrich_practices'
)
def enrich_practices_task(
    self,
    run_id: int,
    limit: Optional[int] = None,
    max_workers: Optional[int] = None
) -> Dict:
    """
    Celery task to enrich DPC practices.

    Args:
        run_id: Enrichment run ID
        limit: Optional limit on number of practices to process
        max_workers: Number of concurrent workers (default from config)

    Returns:
        Final statistics dictionary
    """
    # Use asyncio to run the enrichment
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(
            _enrich_practices_async(
                task=self,
                run_id=run_id,
                limit=limit,
                max_workers=max_workers or MAX_WORKERS
            )
        )
        return result

    finally:
        loop.close()


async def _enrich_practices_async(
    task: Task,
    run_id: int,
    limit: Optional[int],
    max_workers: int
) -> Dict:
    """
    Async enrichment logic with database integration.

    Args:
        task: Celery task instance
        run_id: Enrichment run ID
        limit: Optional limit on number of practices
        max_workers: Number of concurrent workers

    Returns:
        Final statistics dictionary
    """
    import sys
    from pathlib import Path

    # Add project root to path if not already there
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from app import create_app

    # Create Flask app context
    app = create_app()

    with app.app_context():
        # Get enrichment run
        run = db.session.query(EnrichmentRun).get(run_id)
        if not run:
            raise ValueError(f"Enrichment run {run_id} not found")

        # Update run status
        run.status = 'running'
        run.started_at = datetime.utcnow()
        db.session.commit()

        # Publish start event
        publish_progress(
            ProgressEvent.STARTED,
            run_id,
            {
                'run_id': run_id,
                'limit': limit,
                'max_workers': max_workers
            }
        )

        try:
            # Get practices to enrich
            practices_query = db.session.query(Practice).filter(
                Practice.enrichment_status.in_(['pending', 'failed', 'skipped'])
            )

            if limit:
                practices_query = practices_query.limit(limit)

            practices = practices_query.all()
            total_practices = len(practices)

            run.total_practices = total_practices
            db.session.commit()

            logger.info(f"Starting enrichment run {run_id}: {total_practices} practices")

            # Convert database practices to dict format for orchestrator
            practices_data = [
                {
                    'practice_id': p.practice_id,
                    'practice_name': p.practice_name,
                    'website_url': p.website_url,
                    'enrichment_level': 'partial',  # Mark as partial so orchestrator processes them
                    **(p.data or {})  # Merge any existing enriched data
                }
                for p in practices
            ]

            # Create temporary directories for this run
            temp_dir = Path('temp') / f'run_{run_id}'
            temp_dir.mkdir(parents=True, exist_ok=True)

            input_file = temp_dir / 'input.json'
            output_file = temp_dir / 'output.json'
            markdown_dir = temp_dir / 'markdown'
            progress_file = temp_dir / 'progress.json'

            markdown_dir.mkdir(parents=True, exist_ok=True)

            # Clean up old progress/output files to prevent resume from stale data
            # (resume=False in orchestrator, so we want fresh runs)
            if progress_file.exists():
                progress_file.unlink()
                logger.info(f"Removed old progress file for fresh run")
            if output_file.exists():
                output_file.unlink()
                logger.info(f"Removed old output file for fresh run")

            # Create wrapper orchestrator with database callbacks
            orchestrator = DatabaseIntegratedOrchestrator(
                openrouter_api_key=OPENROUTER_API_KEY,
                input_file=input_file,
                output_file=output_file,
                markdown_dir=markdown_dir,
                progress_file=progress_file,
                max_workers=max_workers,
                checkpoint_interval=CHECKPOINT_INTERVAL,
                limit=limit,
                run_id=run_id,
                db_session=db.session,
                practices_data=practices_data
            )

            # Initialize stats cache with total_practices before starting
            # This ensures the progress tab shows correct total even before first practice completes
            initial_stats = {
                'total_practices': total_practices,
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'success_rate': '0.0%',
                'total_cost': '$0.00'
            }
            update_stats_cache(run_id, initial_stats)

            # Publish initial stats via SSE
            publish_progress(
                ProgressEvent.STATS_UPDATE,
                run_id,
                {
                    'total': total_practices,
                    'completed': 0,
                    'failed': 0,
                    'skipped': 0,
                    'cost': 0
                }
            )

            # Run enrichment
            stats = await orchestrator.run()

            # Update final run status
            run.status = 'completed'
            run.completed_at = datetime.utcnow()
            run.successful = stats['successful']
            run.failed = stats['failed']

            # Parse total_cost - handle both numeric and formatted string values
            total_cost = stats.get('total_cost', 0)
            if isinstance(total_cost, str):
                # Remove $ and convert to float
                total_cost = float(total_cost.replace('$', '').replace(',', ''))
            run.total_cost = total_cost

            run.statistics = stats
            db.session.commit()

            # Publish completion event
            publish_progress(
                ProgressEvent.COMPLETED,
                run_id,
                {
                    'run_id': run_id,
                    'stats': stats,
                    'completed_at': run.completed_at.isoformat()
                }
            )

            # Clear control flags
            clear_run_control(run_id)

            logger.info(f"Enrichment run {run_id} completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Enrichment run {run_id} failed: {e}", exc_info=True)

            # Update run status
            run.status = 'failed'
            run.completed_at = datetime.utcnow()
            run.statistics = {'error': str(e)}
            db.session.commit()

            # Publish error event
            publish_progress(
                ProgressEvent.ERROR,
                run_id,
                {
                    'run_id': run_id,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )

            raise


class DatabaseIntegratedOrchestrator(EnrichmentOrchestrator):
    """
    Extended orchestrator with database integration.

    Inherits from EnrichmentOrchestrator and adds:
    - Database updates after each practice
    - Real-time progress publishing
    - Pause/resume control via Redis
    """

    def __init__(
        self,
        openrouter_api_key: str,
        input_file: Path,
        output_file: Path,
        markdown_dir: Path,
        progress_file: Path,
        max_workers: int,
        checkpoint_interval: int,
        limit: Optional[int],
        run_id: int,
        db_session: Session,
        practices_data: List[Dict]
    ):
        """
        Initialize with database integration.

        Args:
            run_id: Enrichment run database ID
            db_session: SQLAlchemy session
            practices_data: List of practice dictionaries
            ... (other args inherited from parent)
        """
        # Write practices data to temporary input file in expected format
        # Orchestrator expects dict with 'metadata' and 'practices' keys
        import json
        input_data = {
            'metadata': {
                'source': 'database',
                'run_id': run_id,
                'total_practices': len(practices_data)
            },
            'practices': practices_data
        }
        with open(input_file, 'w') as f:
            json.dump(input_data, f, indent=2)

        # Debug: Log what we wrote
        logger.info(f"Wrote input file with {len(practices_data)} practices, keys: {list(input_data.keys())}")

        # Initialize parent orchestrator
        super().__init__(
            openrouter_api_key=openrouter_api_key,
            input_file=input_file,
            output_file=output_file,
            markdown_dir=markdown_dir,
            progress_file=progress_file,
            max_workers=max_workers,
            checkpoint_interval=checkpoint_interval,
            resume=False,
            limit=limit
        )

        self.run_id = run_id
        self.db_session = db_session
        self._pause_requested = False

    async def _enrich_practice_impl(self, practice: Dict):
        """
        Override parent implementation to add database updates and progress publishing.

        This is the actual implementation that gets called with timeout wrapper.

        Args:
            practice: Practice data dict
        """
        practice_id = practice['practice_id']

        # Check for pause/stop control
        control = get_run_control(self.run_id)
        if control == 'pause':
            logger.info(f"Pause requested for run {self.run_id}")
            publish_progress(
                ProgressEvent.PAUSED,
                self.run_id,
                {'practice_id': practice_id}
            )
            # Wait until resumed or stopped
            while get_run_control(self.run_id) == 'pause':
                await asyncio.sleep(1)

            if get_run_control(self.run_id) == 'resume':
                logger.info(f"Resuming run {self.run_id}")
                publish_progress(
                    ProgressEvent.RESUMED,
                    self.run_id,
                    {'practice_id': practice_id}
                )
                clear_run_control(self.run_id)

        elif control == 'stop':
            logger.info(f"Stop requested for run {self.run_id}")
            raise KeyboardInterrupt("Enrichment stopped by user")

        # Update practice status to in_progress
        db_practice = self.db_session.query(Practice).filter_by(
            practice_id=practice_id
        ).first()

        if db_practice:
            db_practice.enrichment_status = 'in_progress'
            self.db_session.commit()

        # Publish practice started event
        publish_progress(
            ProgressEvent.PRACTICE_STARTED,
            self.run_id,
            {
                'practice_id': practice_id,
                'practice_name': practice.get('practice_name', ''),
                'website_url': practice.get('website_url', '')
            }
        )

        # Run parent enrichment logic (the implementation, not the timeout wrapper)
        try:
            await super()._enrich_practice_impl(practice)

            # Check the practice status in progress tracker
            # (parent method may return early without exception if scraping failed)
            from src.enrichment_v2.utils.progress import PracticeStatus
            actual_status = self.progress_tracker.get_status(practice_id)

            # If the practice failed or was skipped, update database accordingly
            if actual_status == PracticeStatus.FAILED:
                if db_practice:
                    db_practice.enrichment_status = 'failed'
                    progress_info = self.progress_tracker.get_progress(practice_id)
                    db_practice.data = {'error': progress_info.error_message if progress_info else 'Enrichment failed'}
                    self.db_session.commit()
                    logger.info(f"Marked practice {practice_id} as failed (from progress tracker)")

                # Publish failure event
                publish_progress(
                    ProgressEvent.PRACTICE_FAILED,
                    self.run_id,
                    {
                        'practice_id': practice_id,
                        'practice_name': practice.get('practice_name', ''),
                        'error': progress_info.error_message if progress_info else 'Scraping failed',
                        'error_type': 'ScrapingError'
                    }
                )
                return

            elif actual_status == PracticeStatus.SKIPPED:
                if db_practice:
                    db_practice.enrichment_status = 'skipped'
                    progress_info = self.progress_tracker.get_progress(practice_id)
                    db_practice.data = {'reason': progress_info.error_message if progress_info else 'Practice skipped'}
                    self.db_session.commit()
                    logger.info(f"Marked practice {practice_id} as skipped (from progress tracker)")

                # Publish skipped event
                publish_progress(
                    ProgressEvent.PRACTICE_SKIPPED,
                    self.run_id,
                    {
                        'practice_id': practice_id,
                        'practice_name': practice.get('practice_name', ''),
                        'error': progress_info.error_message if progress_info else 'Practice skipped'
                    }
                )
                return

            # If successful, update database
            if db_practice and actual_status == PracticeStatus.SUCCESS:
                # Get enriched data from the latest saved practice
                enriched_data = None
                async with self._enriched_lock:
                    # Find the enriched practice that was just added
                    for ep in reversed(self._enriched_practices):
                        if ep.get('practice_id') == practice_id:
                            enriched_data = ep
                            break

                if enriched_data:
                    db_practice.enrichment_status = 'completed'
                    db_practice.enriched_at = datetime.utcnow()
                    db_practice.data = enriched_data
                    self.db_session.commit()

                    # Extract quality metrics
                    metadata = enriched_data.get('_enrichment_metadata', {})
                    field_count = sum(
                        1 for k, v in enriched_data.items()
                        if not k.startswith('_') and v not in (None, '', [], {})
                    )

                    # Publish completion event
                    publish_progress(
                        ProgressEvent.PRACTICE_COMPLETED,
                        self.run_id,
                        {
                            'practice_id': practice_id,
                            'practice_name': practice.get('practice_name', ''),
                            'field_count': field_count,
                            'cost': metadata.get('llm_cost', 0),
                            'pages_crawled': metadata.get('pages_crawled', 0),
                            'scraper_method': metadata.get('scraper_method', ''),
                            'data': enriched_data  # Full data for preview
                        }
                    )

            # Update stats cache
            update_stats_cache(self.run_id, self.stats.to_dict())

        except Exception as e:
            # Update practice as failed in database
            if db_practice:
                try:
                    # Rollback any pending transaction to ensure clean state
                    self.db_session.rollback()

                    # Refresh the practice object from database
                    self.db_session.refresh(db_practice)

                    # Update status to failed
                    db_practice.enrichment_status = 'failed'
                    db_practice.data = {'error': str(e)}
                    self.db_session.commit()
                    logger.info(f"Marked practice {practice_id} as failed in database")
                except Exception as db_error:
                    logger.error(f"Failed to update practice status in database: {db_error}")
                    self.db_session.rollback()

            # Publish failure event
            publish_progress(
                ProgressEvent.PRACTICE_FAILED,
                self.run_id,
                {
                    'practice_id': practice_id,
                    'practice_name': practice.get('practice_name', ''),
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )

            # Re-raise to let parent handle it
            raise

    async def run(self):
        """
        Override run method to sync all practice statuses after completion.
        """
        # Run parent enrichment
        result = await super().run()

        # After enrichment, sync all practice statuses from progress tracker to database
        try:
            self._sync_practice_statuses()
        except Exception as e:
            logger.error(f"Failed to sync practice statuses: {e}")

        return result

    def _sync_practice_statuses(self):
        """
        Sync practice statuses from progress tracker to database.

        This ensures skipped/failed practices that weren't caught
        in the main enrichment loop get their statuses updated.
        """
        logger.info("Syncing practice statuses from progress tracker to database...")

        # Get progress tracker state
        from src.enrichment_v2.utils.progress import ProgressTracker, PracticeStatus

        tracker = ProgressTracker(self.progress_file)

        # Map progress tracker status to database status
        status_mapping = {
            PracticeStatus.SUCCESS: 'completed',
            PracticeStatus.FAILED: 'failed',
            PracticeStatus.SKIPPED: 'skipped',
            PracticeStatus.IN_PROGRESS: 'in_progress',
            PracticeStatus.PENDING: 'pending'
        }

        synced = 0

        # Iterate through all practices in the tracker
        with tracker._lock:
            for practice_id, progress in tracker._practices.items():
                db_practice = self.db_session.query(Practice).filter_by(
                    practice_id=practice_id
                ).first()

                if not db_practice:
                    continue

                status = progress.status
                db_status = status_mapping.get(status)

                if db_status and db_practice.enrichment_status != db_status:
                    # Don't overwrite completed status
                    if db_practice.enrichment_status != 'completed':
                        db_practice.enrichment_status = db_status
                        synced += 1

        if synced > 0:
            self.db_session.commit()
            logger.info(f"Synced {synced} practice statuses to database")
        else:
            logger.info("All practice statuses already in sync")
