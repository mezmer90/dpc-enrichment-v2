"""
Markdown storage system

Saves scraped markdown content to organized directory structure.

Structure:
data/markdown/{practice_id}/
├── page_1_homepage.md
├── page_2_about.md
├── ...
├── merged.md
└── metadata.json
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

from ..scraper.base_scraper import PageContent, ScraperResult

logger = logging.getLogger(__name__)


class MarkdownStorage:
    """
    Manages storage of markdown files for practices.

    Creates organized directory structure with individual page files
    and merged content.
    """

    def __init__(self, base_dir: Path):
        """
        Initialize markdown storage.

        Args:
            base_dir: Base directory for markdown storage (e.g., data/markdown/)
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Markdown storage initialized: {self.base_dir}")

    def save_scraper_result(
        self,
        practice_id: str,
        result: ScraperResult,
        merged_markdown: Optional[str] = None
    ):
        """
        Save complete scraper result for a practice.

        Args:
            practice_id: Unique practice identifier
            result: ScraperResult with all scraped pages
            merged_markdown: Optional pre-merged markdown (if None, will merge pages)
        """
        practice_dir = self._get_practice_dir(practice_id)

        # Save individual pages
        self.save_pages(practice_id, result.pages)

        # Save merged markdown
        if merged_markdown:
            self.save_merged(practice_id, merged_markdown)
        elif result.pages:
            # Merge pages if not provided
            merged = result.get_merged_markdown()
            self.save_merged(practice_id, merged)

        # Save metadata
        self._save_metadata(practice_id, result)

        # Log with appropriate level based on content
        if result.total_markdown_chars == 0:
            logger.warning(
                f"Saved markdown for {practice_id}: {len(result.pages)} pages, 0 chars - "
                f"EMPTY CONTENT - Possible causes: (1) Markdown conversion failed, "
                f"(2) Cloudflare/bot blocking, (3) JS rendering failed, (4) Pages have no text content"
            )
        else:
            logger.info(
                f"Saved markdown for {practice_id}: {len(result.pages)} pages, "
                f"{result.total_markdown_chars} chars"
            )

    def save_pages(self, practice_id: str, pages: List[PageContent]):
        """
        Save individual page markdown files.

        Args:
            practice_id: Practice identifier
            pages: List of PageContent objects
        """
        practice_dir = self._get_practice_dir(practice_id)

        for i, page in enumerate(pages, 1):
            # Create filename from page title
            title_slug = self._sanitize_filename(page.title or f"page_{i}")
            filename = f"page_{i}_{title_slug}.md"

            # Save markdown
            file_path = practice_dir / filename
            file_path.write_text(page.markdown, encoding='utf-8')

            logger.debug(f"Saved page {i}/{len(pages)}: {filename}")

    def save_merged(self, practice_id: str, merged_markdown: str):
        """
        Save merged markdown file.

        Args:
            practice_id: Practice identifier
            merged_markdown: Merged markdown content from all pages
        """
        practice_dir = self._get_practice_dir(practice_id)
        merged_path = practice_dir / "merged.md"

        merged_path.write_text(merged_markdown, encoding='utf-8')
        logger.debug(f"Saved merged markdown: {len(merged_markdown)} chars")

    def load_merged(self, practice_id: str) -> Optional[str]:
        """
        Load merged markdown for a practice.

        Args:
            practice_id: Practice identifier

        Returns:
            Merged markdown content, or None if not found
        """
        practice_dir = self.base_dir / practice_id
        merged_path = practice_dir / "merged.md"

        if not merged_path.exists():
            logger.warning(f"No merged markdown found for {practice_id}")
            return None

        return merged_path.read_text(encoding='utf-8')

    def practice_exists(self, practice_id: str) -> bool:
        """
        Check if markdown exists for practice.

        Args:
            practice_id: Practice identifier

        Returns:
            True if practice directory exists
        """
        practice_dir = self.base_dir / practice_id
        return practice_dir.exists() and (practice_dir / "merged.md").exists()

    def get_practice_stats(self, practice_id: str) -> Optional[Dict]:
        """
        Get statistics for stored markdown.

        Args:
            practice_id: Practice identifier

        Returns:
            Dict with stats, or None if not found
        """
        if not self.practice_exists(practice_id):
            return None

        practice_dir = self.base_dir / practice_id
        merged_path = practice_dir / "merged.md"

        page_files = list(practice_dir.glob("page_*.md"))
        merged_chars = len(merged_path.read_text(encoding='utf-8')) if merged_path.exists() else 0

        return {
            'practice_id': practice_id,
            'total_pages': len(page_files),
            'merged_chars': merged_chars,
            'directory': str(practice_dir),
            'has_metadata': (practice_dir / "metadata.json").exists()
        }

    def _get_practice_dir(self, practice_id: str) -> Path:
        """Get practice directory, creating if necessary"""
        practice_dir = self.base_dir / practice_id
        practice_dir.mkdir(parents=True, exist_ok=True)
        return practice_dir

    def _save_metadata(self, practice_id: str, result: ScraperResult):
        """Save scraping metadata"""
        practice_dir = self._get_practice_dir(practice_id)
        metadata_path = practice_dir / "metadata.json"

        metadata = {
            'practice_id': practice_id,
            'scraped_at': datetime.now().isoformat(),
            'scraper_method': result.method.value,
            'pages_crawled': result.pages_crawled,
            'total_time': result.total_time,
            'bytes_downloaded': result.bytes_downloaded,
            'total_markdown_chars': result.total_markdown_chars,
            'page_urls': [page.url for page in result.pages],
            'page_titles': [page.title for page in result.pages],
            'status': result.status.value,
            'error_message': result.error_message,
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """
        Create safe filename from page title.

        Args:
            name: Original filename/title

        Returns:
            Sanitized filename (max 50 chars, safe characters only)
        """
        # Replace unsafe characters
        safe = "".join(
            c if c.isalnum() or c in (' ', '-', '_') else '_'
            for c in name
        )

        # Remove extra spaces/underscores
        safe = '_'.join(safe.split())

        # Truncate to reasonable length
        return safe[:50].strip('_')

    def get_all_practice_ids(self) -> List[str]:
        """
        Get list of all practice IDs with stored markdown.

        Returns:
            List of practice IDs
        """
        practice_ids = []

        for practice_dir in self.base_dir.iterdir():
            if practice_dir.is_dir() and (practice_dir / "merged.md").exists():
                practice_ids.append(practice_dir.name)

        return practice_ids

    def cleanup_practice(self, practice_id: str):
        """
        Delete all markdown files for a practice.

        Args:
            practice_id: Practice identifier
        """
        practice_dir = self.base_dir / practice_id

        if practice_dir.exists():
            import shutil
            shutil.rmtree(practice_dir)
            logger.info(f"Deleted markdown for {practice_id}")
