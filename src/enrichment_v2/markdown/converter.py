"""
Markdown converter with multiple fallback methods

Converts HTML to Markdown using 4 methods in priority order:
1. crawl4ai (if available from scraper result)
2. html2text library
3. markdownify library
4. Custom HTML stripper (fallback - extracts plain text)

Ensures data is never lost by always falling back to plain text extraction.
"""

import logging
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class MarkdownConverter:
    """
    Converts HTML to Markdown with multiple fallback methods.

    Implements cascading fallback strategy to ensure data is always extracted.
    """

    @staticmethod
    def convert(
        html: str,
        method: str = 'auto',
        preserve_images: bool = True,
        preserve_links: bool = True
    ) -> str:
        """
        Convert HTML to Markdown.

        Args:
            html: HTML content to convert
            method: Conversion method ('auto', 'html2text', 'markdownify', 'custom')
            preserve_images: Keep image references
            preserve_links: Keep hyperlinks

        Returns:
            Markdown content (never fails, worst case returns plain text)
        """
        if not html or not html.strip():
            return ""

        if method == 'auto':
            # Try all methods in order
            for m in ['html2text', 'markdownify', 'custom']:
                try:
                    result = MarkdownConverter._convert_with_method(
                        html, m, preserve_images, preserve_links
                    )
                    if result and result.strip():
                        return result
                except Exception as e:
                    logger.debug(f"Method {m} failed: {e}")
                    continue

            # Final fallback: custom stripper
            return MarkdownConverter._custom_stripper(html)

        else:
            # Specific method requested
            return MarkdownConverter._convert_with_method(
                html, method, preserve_images, preserve_links
            )

    @staticmethod
    def _convert_with_method(
        html: str,
        method: str,
        preserve_images: bool,
        preserve_links: bool
    ) -> str:
        """Convert using specific method"""
        if method == 'html2text':
            return MarkdownConverter._html2text(html, preserve_images, preserve_links)
        elif method == 'markdownify':
            return MarkdownConverter._markdownify(html, preserve_images, preserve_links)
        elif method == 'custom':
            return MarkdownConverter._custom_stripper(html)
        else:
            raise ValueError(f"Unknown conversion method: {method}")

    @staticmethod
    def _html2text(html: str, preserve_images: bool, preserve_links: bool) -> str:
        """
        Convert using html2text library.

        Pros: Good markdown output, handles complex HTML
        Cons: Can be slow on large HTML
        """
        try:
            import html2text

            h = html2text.HTML2Text()
            h.ignore_links = not preserve_links
            h.ignore_images = not preserve_images
            h.body_width = 0  # No line wrapping
            h.unicode_snob = True
            h.ignore_emphasis = False
            h.skip_internal_links = False

            markdown = h.handle(html)
            logger.debug("Converted HTML to markdown using html2text")
            return markdown

        except ImportError:
            logger.warning("html2text not installed, trying next method")
            raise
        except Exception as e:
            logger.warning(f"html2text conversion failed: {e}")
            raise

    @staticmethod
    def _markdownify(html: str, preserve_images: bool, preserve_links: bool) -> str:
        """
        Convert using markdownify library.

        Pros: Clean markdown output
        Cons: Less configurable than html2text
        """
        try:
            from markdownify import markdownify as md

            markdown = md(
                html,
                heading_style="ATX",
                bullets="-",
                strip=["script", "style"],
            )
            logger.debug("Converted HTML to markdown using markdownify")
            return markdown

        except ImportError:
            logger.warning("markdownify not installed, trying next method")
            raise
        except Exception as e:
            logger.warning(f"markdownify conversion failed: {e}")
            raise

    @staticmethod
    def _custom_stripper(html: str) -> str:
        """
        Custom HTML stripper - extracts plain text.

        This is the ultimate fallback that never fails.
        Removes scripts, styles, and extracts clean text.

        Pros: Always works, no dependencies
        Cons: Loses formatting, links, images
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for element in soup(['script', 'style', 'noscript', 'iframe']):
                element.decompose()

            # Get text
            text = soup.get_text(separator='\n', strip=True)

            # Clean up multiple blank lines
            lines = [line.strip() for line in text.splitlines()]
            lines = [line for line in lines if line]  # Remove empty lines

            markdown = '\n\n'.join(lines)
            logger.debug("Converted HTML to text using custom stripper (fallback)")
            return markdown

        except Exception as e:
            logger.error(f"Even custom stripper failed: {e}")
            # Last resort: just return the raw HTML
            return html

    @staticmethod
    def clean_markdown(markdown: str) -> str:
        """
        Clean and normalize markdown content.

        Removes excessive whitespace, normalizes line breaks, etc.

        Args:
            markdown: Markdown content to clean

        Returns:
            Cleaned markdown
        """
        if not markdown:
            return ""

        # Split into lines
        lines = markdown.splitlines()

        # Remove excessive blank lines (more than 2 consecutive)
        cleaned_lines = []
        blank_count = 0

        for line in lines:
            stripped = line.strip()

            if not stripped:
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append("")
            else:
                blank_count = 0
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines).strip()

    @staticmethod
    def extract_text_only(html: str) -> str:
        """
        Extract only text content (no markdown formatting).

        Useful for content analysis or when markdown is not needed.

        Args:
            html: HTML content

        Returns:
            Plain text content
        """
        soup = BeautifulSoup(html, 'html.parser')

        for element in soup(['script', 'style', 'noscript']):
            element.decompose()

        return soup.get_text(separator=' ', strip=True)

    @staticmethod
    def get_available_methods() -> list[str]:
        """
        Get list of available conversion methods.

        Returns:
            List of method names that are available (dependencies installed)
        """
        available = ['custom']  # Always available

        try:
            import html2text
            available.append('html2text')
        except ImportError:
            pass

        try:
            from markdownify import markdownify
            available.append('markdownify')
        except ImportError:
            pass

        return available
