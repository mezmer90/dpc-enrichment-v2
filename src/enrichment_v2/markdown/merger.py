"""
Markdown merger for combining multi-page content

Merges multiple pages into a single comprehensive markdown document.
"""

from typing import List
import logging

from ..scraper.base_scraper import PageContent

logger = logging.getLogger(__name__)


class MarkdownMerger:
    """
    Merges multiple PageContent objects into single markdown document.

    Creates well-structured document with:
    - Table of contents
    - Page separators
    - Metadata preservation
    """

    @staticmethod
    def merge_pages(
        pages: List[PageContent],
        include_toc: bool = True,
        include_metadata: bool = False
    ) -> str:
        """
        Merge multiple pages into single markdown document.

        Args:
            pages: List of PageContent objects to merge
            include_toc: Include table of contents at top
            include_metadata: Include metadata for each page

        Returns:
            Merged markdown content
        """
        if not pages:
            return ""

        if len(pages) == 1:
            # Single page, just return its markdown
            return pages[0].markdown

        sections = []

        # Add table of contents
        if include_toc:
            toc = MarkdownMerger.create_table_of_contents(pages)
            sections.append(toc)
            sections.append("\n\n")

        # Add each page
        for i, page in enumerate(pages, 1):
            section = MarkdownMerger._create_page_section(
                page,
                page_number=i,
                include_metadata=include_metadata
            )
            sections.append(section)

        # Join all sections
        merged = "\n\n".join(sections)

        logger.debug(f"Merged {len(pages)} pages into {len(merged)} characters")
        return merged

    @staticmethod
    def create_table_of_contents(pages: List[PageContent]) -> str:
        """
        Create table of contents from pages.

        Args:
            pages: List of pages

        Returns:
            TOC markdown
        """
        toc_lines = ["# Table of Contents\n"]

        for i, page in enumerate(pages, 1):
            title = page.title or f"Page {i}"
            # Clean title (remove special chars for anchor)
            anchor = MarkdownMerger._create_anchor(title)
            toc_lines.append(f"{i}. [{title}](#{anchor}) - {page.url}")

        return "\n".join(toc_lines)

    @staticmethod
    def _create_page_section(
        page: PageContent,
        page_number: int,
        include_metadata: bool
    ) -> str:
        """Create section for a single page"""
        lines = []

        # Page header
        separator = "=" * 80
        lines.append(separator)

        # Title
        title = page.title or f"Page {page_number}"
        anchor = MarkdownMerger._create_anchor(title)
        lines.append(f"## {title} {{#{anchor}}}")

        # URL
        lines.append(f"**URL:** {page.url}")

        # Metadata (optional)
        if include_metadata:
            lines.append(f"**Load Time:** {page.load_time:.2f}s")
            lines.append(f"**Status Code:** {page.status_code}")

            if page.metadata:
                lines.append(f"**Metadata:** {page.metadata}")

        lines.append(separator)
        lines.append("")  # Blank line

        # Content
        lines.append(page.markdown)

        return "\n".join(lines)

    @staticmethod
    def _create_anchor(text: str) -> str:
        """
        Create URL-safe anchor from text.

        Args:
            text: Text to convert

        Returns:
            URL-safe anchor string
        """
        # Convert to lowercase
        anchor = text.lower()

        # Replace spaces and special chars with hyphens
        anchor = "".join(
            c if c.isalnum() or c in (' ', '-', '_') else '-'
            for c in anchor
        )

        # Replace multiple hyphens with single
        while '--' in anchor:
            anchor = anchor.replace('--', '-')

        # Remove leading/trailing hyphens
        anchor = anchor.strip('-')

        return anchor

    @staticmethod
    def merge_markdown_strings(markdowns: List[str], separator: str = "\n\n---\n\n") -> str:
        """
        Merge raw markdown strings (simpler version).

        Args:
            markdowns: List of markdown strings
            separator: Separator between documents

        Returns:
            Merged markdown
        """
        return separator.join(md for md in markdowns if md and md.strip())

    @staticmethod
    def get_page_statistics(pages: List[PageContent]) -> dict:
        """
        Get statistics about pages.

        Args:
            pages: List of pages

        Returns:
            Statistics dict
        """
        if not pages:
            return {
                'total_pages': 0,
                'total_markdown_chars': 0,
                'total_html_chars': 0,
                'average_load_time': 0.0,
            }

        return {
            'total_pages': len(pages),
            'total_markdown_chars': sum(len(p.markdown) for p in pages),
            'total_html_chars': sum(len(p.html) for p in pages),
            'average_load_time': sum(p.load_time for p in pages) / len(pages),
            'titles': [p.title or 'Untitled' for p in pages],
            'urls': [p.url for p in pages],
        }
