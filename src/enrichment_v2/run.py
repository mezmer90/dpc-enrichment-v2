"""
Main entry point for Enrichment System V2

Usage:
    python run.py --input data/processed/dpc_complete.json --api-key YOUR_KEY
    python run.py --resume  # Resume previous run
    python run.py --use-pooled-first  # Process pooled practices first
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from .orchestrator import EnrichmentOrchestrator
from .config import (
    MAX_WORKERS,
    CHECKPOINT_INTERVAL,
    DEFAULT_INPUT_FILE,
    DEFAULT_OUTPUT_FILE,
    DEFAULT_MARKDOWN_DIR,
    DEFAULT_PROGRESS_FILE
)


def setup_logging(log_file: Path, verbose: bool = False, quiet: bool = False):
    """
    Setup logging configuration.

    Args:
        log_file: Log file path
        verbose: Enable verbose (DEBUG) logging
        quiet: Minimal console output (WARNING+ only)
    """
    # File always gets INFO or DEBUG
    file_level = logging.DEBUG if verbose else logging.INFO

    # Console gets INFO by default (shows progress), DEBUG if verbose, ERROR if quiet
    if quiet:
        console_level = logging.ERROR
    elif verbose:
        console_level = logging.DEBUG
    else:
        console_level = logging.INFO  # Shows progress updates

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # File handler (full logs)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(file_formatter)

    # Console handler (cleaner output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Silence noisy third-party libraries
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('selenium').setLevel(logging.ERROR)
    logging.getLogger('playwright').setLevel(logging.ERROR)
    logging.getLogger('openai').setLevel(logging.ERROR)
    logging.getLogger('httpx').setLevel(logging.ERROR)
    logging.getLogger('httpcore').setLevel(logging.ERROR)
    logging.getLogger('WDM').setLevel(logging.ERROR)  # WebDriver Manager
    logging.getLogger('webdriver_manager').setLevel(logging.ERROR)

    return logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='DPC Enrichment System V2 - Comprehensive practice enrichment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fresh run with default settings
  python run.py --api-key YOUR_OPENROUTER_KEY

  # Resume previous run
  python run.py --api-key YOUR_KEY --resume

  # Process pooled practices first
  python run.py --api-key YOUR_KEY --use-pooled-first

  # Custom input/output files
  python run.py --api-key YOUR_KEY \\
    --input data/processed/custom.json \\
    --output data/enriched/custom_out.json

  # High concurrency for fast execution
  python run.py --api-key YOUR_KEY --max-workers 20

  # Verbose logging for debugging
  python run.py --api-key YOUR_KEY --verbose
        """
    )

    # Required arguments
    parser.add_argument(
        '--api-key',
        type=str,
        required=True,
        help='OpenRouter API key for Gemini 2.5 Flash'
    )

    # Input/Output files
    parser.add_argument(
        '--input',
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help=f'Input JSON file with practice data (default: {DEFAULT_INPUT_FILE})'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f'Output JSON file for enriched data (default: {DEFAULT_OUTPUT_FILE})'
    )
    parser.add_argument(
        '--markdown-dir',
        type=Path,
        default=DEFAULT_MARKDOWN_DIR,
        help=f'Directory for markdown storage (default: {DEFAULT_MARKDOWN_DIR})'
    )
    parser.add_argument(
        '--progress-file',
        type=Path,
        default=DEFAULT_PROGRESS_FILE,
        help=f'Progress tracking file (default: {DEFAULT_PROGRESS_FILE})'
    )

    # Execution options
    parser.add_argument(
        '--max-workers',
        type=int,
        default=MAX_WORKERS,
        help=f'Maximum concurrent workers (default: {MAX_WORKERS})'
    )
    parser.add_argument(
        '--checkpoint-interval',
        type=int,
        default=CHECKPOINT_INTERVAL,
        help=f'Save progress every N practices (default: {CHECKPOINT_INTERVAL})'
    )
    parser.add_argument(
        '--use-pooled-first',
        action='store_true',
        help='Process pooled practices before non-pooled'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from previous run (process pending and failed)'
    )

    # Logging
    parser.add_argument(
        '--log-file',
        type=Path,
        default=Path('logs/enrichment_v2.log'),
        help='Log file path (default: logs/enrichment_v2.log)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose (DEBUG) logging - shows all details'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimal console output - only errors (logs still saved to file)'
    )

    # Testing
    parser.add_argument(
        '--test-connection',
        action='store_true',
        help='Test API connection and exit'
    )

    return parser.parse_args()


async def test_connection(api_key: str, logger):
    """
    Test API connection.

    Args:
        api_key: OpenRouter API key
        logger: Logger instance
    """
    from .ai.gemini_client import GeminiClient

    logger.info("Testing API connection...")

    try:
        client = GeminiClient(api_key=api_key)
        success = await client.test_connection()

        if success:
            logger.info("[SUCCESS] API connection successful")
            model_info = client.get_model_info()
            logger.info(f"Model: {model_info['model']}")
            logger.info(f"Context: {model_info['context_window']}")
            logger.info(f"Pricing: Input={model_info['pricing']['input']}, Output={model_info['pricing']['output']}")
            return True
        else:
            logger.error("[FAILED] API connection failed")
            return False

    except Exception as e:
        logger.error(f"[ERROR] API connection error: {e}")
        return False


async def main():
    """Main entry point"""
    # Parse arguments
    args = parse_args()

    # Setup logging
    logger = setup_logging(args.log_file, args.verbose, args.quiet)

    logger.info("=" * 80)
    logger.info("DPC ENRICHMENT SYSTEM V2")
    logger.info("=" * 80)
    logger.info(f"Input: {args.input}")
    logger.info(f"Output: {args.output}")
    logger.info(f"Markdown Dir: {args.markdown_dir}")
    logger.info(f"Progress File: {args.progress_file}")
    logger.info(f"Max Workers: {args.max_workers}")
    logger.info(f"Resume Mode: {args.resume}")
    logger.info(f"Pooled First: {args.use_pooled_first}")
    logger.info("=" * 80)

    # Test connection mode
    if args.test_connection:
        success = await test_connection(args.api_key, logger)
        sys.exit(0 if success else 1)

    # Validate input file
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    try:
        # Initialize orchestrator
        orchestrator = EnrichmentOrchestrator(
            openrouter_api_key=args.api_key,
            input_file=args.input,
            output_file=args.output,
            markdown_dir=args.markdown_dir,
            progress_file=args.progress_file,
            max_workers=args.max_workers,
            checkpoint_interval=args.checkpoint_interval,
            use_pooled_first=args.use_pooled_first,
            resume=args.resume
        )

        # Run enrichment
        logger.info("Starting enrichment pipeline...")
        stats = await orchestrator.run()

        # Print summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("ENRICHMENT SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Practices: {stats['total_practices']}")
        logger.info(f"Successful: {stats['successful']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info(f"Skipped: {stats['skipped']}")
        logger.info(f"Success Rate: {stats['success_rate']}")
        logger.info(f"Total Cost: {stats['total_cost']}")
        logger.info(f"Total Time: {stats['total_time']}")
        logger.info(f"Output File: {args.output}")
        logger.info("=" * 80)

        # Exit code based on success rate
        success_rate = float(stats['success_rate'].rstrip('%'))
        if success_rate >= 90:
            logger.info("[SUCCESS] Enrichment completed successfully!")
            sys.exit(0)
        elif success_rate >= 70:
            logger.warning("[WARNING] Enrichment completed with warnings (70-90% success)")
            sys.exit(0)
        else:
            logger.error("[FAILED] Enrichment completed with low success rate (<70%)")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("\n\nEnrichment interrupted by user")
        logger.info("Progress has been saved. Use --resume to continue.")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Enrichment failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    # Run async main
    asyncio.run(main())
