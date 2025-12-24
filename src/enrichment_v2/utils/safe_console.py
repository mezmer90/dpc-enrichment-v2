"""
Safe Console Output for Windows PowerShell

Handles encoding issues with Windows console (charmap errors)
by sanitizing all output to ASCII-safe characters.
"""

import sys
import logging
from typing import Any


def sanitize_for_console(text: str, errors: str = 'replace') -> str:
    """
    Sanitize text for safe console output on Windows.

    Args:
        text: Input text that may contain Unicode characters
        errors: How to handle encoding errors ('replace', 'ignore', 'backslashreplace')

    Returns:
        ASCII-safe text suitable for Windows console

    Examples:
        >>> sanitize_for_console("Café ☕")
        'Caf? ?'
        >>> sanitize_for_console("Test ✅ passed")
        'Test ? passed'
    """
    if not isinstance(text, str):
        text = str(text)

    try:
        # Try to encode to the console encoding (usually cp1252 or cp437 on Windows)
        console_encoding = sys.stdout.encoding or 'utf-8'
        return text.encode(console_encoding, errors=errors).decode(console_encoding)
    except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
        # Fallback to ASCII with replacement
        return text.encode('ascii', errors='replace').decode('ascii')


class WindowsSafeFormatter(logging.Formatter):
    """
    Custom log formatter that sanitizes all log messages for Windows console.

    Prevents charmap encoding errors when logging Unicode characters
    to Windows PowerShell or Command Prompt.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with Windows-safe encoding"""
        # Format the message normally first
        original_msg = super().format(record)

        # Sanitize for console
        return sanitize_for_console(original_msg)


def safe_print(*args: Any, **kwargs: Any) -> None:
    """
    Windows-safe print function that handles Unicode gracefully.

    Drop-in replacement for print() that won't crash on Unicode characters.

    Args:
        *args: Values to print
        **kwargs: Keyword arguments passed to print()

    Examples:
        >>> safe_print("Processing:", "Café ☕")
        Processing: Caf? ?
        >>> safe_print("Status: ✅ Complete")
        Status: ? Complete
    """
    # Sanitize all arguments
    safe_args = [sanitize_for_console(str(arg)) for arg in args]
    print(*safe_args, **kwargs)


def configure_safe_logging(
    level: int = logging.INFO,
    log_file: str = None,
    console: bool = True
) -> None:
    """
    Configure logging with Windows-safe console output.

    Args:
        level: Logging level (logging.INFO, logging.DEBUG, etc.)
        log_file: Optional log file path (UTF-8 encoding for file)
        console: Whether to enable console logging

    Example:
        >>> configure_safe_logging(
        ...     level=logging.INFO,
        ...     log_file='app.log',
        ...     console=True
        ... )
    """
    handlers = []

    # Console handler with Windows-safe formatter
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(WindowsSafeFormatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        handlers.append(console_handler)

    # File handler with UTF-8 encoding (safe for all characters)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True  # Override any existing configuration
    )


def get_safe_logger(name: str) -> logging.Logger:
    """
    Get a logger configured for Windows-safe output.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance with Windows-safe formatting

    Example:
        >>> logger = get_safe_logger(__name__)
        >>> logger.info("Processing: Café ☕")
        INFO - Processing: Caf? ?
    """
    logger = logging.getLogger(name)

    # Add Windows-safe handler if not already present
    if not any(isinstance(h.formatter, WindowsSafeFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(WindowsSafeFormatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)

    return logger


# Convenience function for testing
def test_console_encoding():
    """Test console encoding with various Unicode characters"""
    test_strings = [
        "Plain ASCII text",
        "Café with accent",
        "Emoji: ✅ ⚠️ 💡 🔄",
        "Japanese: こんにちは",
        "Arabic: مرحبا",
        "Special: © ® ™ € £",
    ]

    print("\n=== Windows Console Encoding Test ===")
    print(f"Console encoding: {sys.stdout.encoding}")
    print("\nOriginal -> Sanitized:")
    print("-" * 50)

    for text in test_strings:
        safe_text = sanitize_for_console(text)
        safe_print(f"{text:30} -> {safe_text}")

    print("\n=== Test Complete ===\n")


if __name__ == '__main__':
    # Run test when executed directly
    test_console_encoding()
