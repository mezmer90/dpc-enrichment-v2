"""
Batch Enrichment Script for V2 System

Enriches 2,077+ partial practices using the v2 enrichment system with:
- ScraperAPI for 98.9% success rate
- Smart URL selection with Gemini AI
- Progressive saving after EVERY practice
- Full crash protection
- Content quality validation

Expected Results:
- 90-95% success rate (1,869-1,973 practices)
- 3-5 hours runtime
- ~$60 total cost
"""

import os
import sys
import asyncio
import logging
import argparse
from pathlib import Path

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        load_dotenv(env_file)
        print(f"[OK] Loaded environment variables from {env_file}")
    else:
        print(f"[!] No .env file found. Please create one from .env.example")
        print(f"    Copy .env.example to .env and add your API keys")
except ImportError:
    print("[!] python-dotenv not installed, skipping .env file loading")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from enrichment_v2.config import (
    OPENROUTER_API_KEY,
    SCRAPERAPI_KEY,
    INPUT_FILE,
    OUTPUT_FILE,
    PROGRESS_FILE
)

# Setup Windows-safe logging
from enrichment_v2.utils.safe_console import WindowsSafeFormatter

# Console handler with Windows-safe formatter
console_handler = logging.StreamHandler()
console_handler.setFormatter(WindowsSafeFormatter('%(asctime)s - %(levelname)s - %(message)s'))

# File handler with UTF-8 encoding (keeps full Unicode in file)
file_handler = logging.FileHandler('batch_enrichment_v2.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)

logger = logging.getLogger(__name__)


def set_environment_variables():
    """Set environment variables for the enrichment run"""
    # Check if API keys are set
    if not OPENROUTER_API_KEY:
        logger.error("=" * 80)
        logger.error("CRITICAL ERROR: OPENROUTER_API_KEY not set!")
        logger.error("=" * 80)
        logger.error("Please set your API key in one of these ways:")
        logger.error("  1. Create a .env file (copy from .env.example)")
        logger.error("  2. Set environment variable: OPENROUTER_API_KEY=your_key")
        logger.error("\nGet your key from: https://openrouter.ai/keys")
        logger.error("=" * 80)
        sys.exit(1)

    if not SCRAPERAPI_KEY:
        logger.error("=" * 80)
        logger.error("CRITICAL ERROR: SCRAPERAPI_KEY not set!")
        logger.error("=" * 80)
        logger.error("Please set your API key in one of these ways:")
        logger.error("  1. Create a .env file (copy from .env.example)")
        logger.error("  2. Set environment variable: SCRAPERAPI_KEY=your_key")
        logger.error("\nGet your key from: https://www.scraperapi.com/")
        logger.error("=" * 80)
        sys.exit(1)

    os.environ['OPENROUTER_API_KEY'] = OPENROUTER_API_KEY
    os.environ['SCRAPERAPI_KEY'] = SCRAPERAPI_KEY
    os.environ['USE_SCRAPING_API'] = 'true'

    logger.info("Environment variables configured:")
    logger.info(f"  OPENROUTER_API_KEY: {'*' * 8} (length: {len(OPENROUTER_API_KEY)})")
    logger.info(f"  SCRAPERAPI_KEY: {'*' * 8} (length: {len(SCRAPERAPI_KEY)})")
    logger.info(f"  USE_SCRAPING_API: true")


def estimate_cost(num_practices: int) -> dict:
    """
    Estimate API costs for enrichment run.

    Args:
        num_practices: Number of practices to enrich

    Returns:
        Dict with cost breakdown
    """
    # ScraperAPI: ~$0.024 per practice (avg 7 pages × ~$0.003/page)
    scraper_cost = num_practices * 0.024

    # URL Selection (Gemini): ~$0.001 per practice
    url_selection_cost = num_practices * 0.001

    # AI Extraction (Gemini): ~$0.005 per practice
    extraction_cost = num_practices * 0.005

    total = scraper_cost + url_selection_cost + extraction_cost

    return {
        'scraper': scraper_cost,
        'url_selection': url_selection_cost,
        'extraction': extraction_cost,
        'total': total,
        'per_practice': total / num_practices
    }


async def main():
    """Run batch enrichment"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Batch enrichment for DPC practices',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with 5 practices first
  python batch_enrich_v2.py --limit 5

  # Test with 20 practices
  python batch_enrich_v2.py --limit 20

  # Full run (all practices)
  python batch_enrich_v2.py
        """
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of practices to process (for testing). Example: --limit 20'
    )
    args = parser.parse_args()

    logger.info("="*80)
    logger.info("BATCH ENRICHMENT V2 - ENHANCED SYSTEM")
    logger.info("="*80)

    # Set environment variables
    set_environment_variables()

    # Import after setting env vars
    from enrichment_v2.orchestrator import EnrichmentOrchestrator
    from enrichment_v2.config import MARKDOWN_DIR, CHECKPOINT_INTERVAL

    # Configuration
    config = {
        'api_key': OPENROUTER_API_KEY,
        'input_file': Path(INPUT_FILE),
        'output_file': Path(OUTPUT_FILE),
        'progress_file': Path(PROGRESS_FILE),
        'markdown_dir': Path(MARKDOWN_DIR),
        'max_workers': 6,  # Parallel workers (very safe, can increase to 8-10 if laptop handles well)
        'checkpoint_interval': 1,  # Save after EVERY practice
        'use_pooled_first': False,
        'resume': True,     # Resume from previous run if exists
        'limit': args.limit,  # Limit for testing
    }

    logger.info("\nConfiguration:")
    logger.info(f"  Input: {config['input_file']}")
    logger.info(f"  Output: {config['output_file']}")
    logger.info(f"  Progress: {config['progress_file']}")
    logger.info(f"  Markdown: {config['markdown_dir']}")
    logger.info(f"  Workers: {config['max_workers']}")
    logger.info(f"  Checkpoint: Every {config['checkpoint_interval']} practice(s)")
    logger.info(f"  Resume: {config['resume']}")
    if config['limit']:
        logger.info(f"  [!] LIMIT: {config['limit']} practices (TEST MODE)")

    logger.info("\nFeatures:")
    logger.info("  [OK] ScraperAPI (98.9% success rate)")
    logger.info("  [OK] Smart URL selector (Gemini AI)")
    logger.info("  [OK] Progressive saving (after EVERY practice)")
    logger.info("  [OK] Content quality validation (2500+ chars)")
    logger.info("  [OK] Crash protection (exit handlers)")
    logger.info("  [OK] Multi-location awareness (providers matched to location)")

    # Load practice count for cost estimation
    from enrichment_v2.storage.data_storage import DataStorage
    practices, _ = DataStorage.load_enriched(config['input_file'])
    total_practices = len(practices)

    # Apply limit if specified
    practices_to_process = config['limit'] if config['limit'] else total_practices

    # Estimate cost
    cost_estimate = estimate_cost(practices_to_process)

    logger.info("\n" + "="*80)
    logger.info("COST ESTIMATE")
    logger.info("="*80)
    logger.info(f"  Practices to process: {practices_to_process:,}")
    logger.info(f"  ScraperAPI (scraping): ~${cost_estimate['scraper']:.2f}")
    logger.info(f"  Gemini (URL selection): ~${cost_estimate['url_selection']:.2f}")
    logger.info(f"  Gemini (data extraction): ~${cost_estimate['extraction']:.2f}")
    logger.info(f"  Total estimated cost: ~${cost_estimate['total']:.2f}")
    logger.info(f"  Cost per practice: ~${cost_estimate['per_practice']:.4f}")

    if config['limit']:
        logger.info(f"\n  [TIP] This is a TEST run with {config['limit']} practices")
        logger.info(f"  [TIP] Full run ({total_practices:,} practices) would cost ~${estimate_cost(total_practices)['total']:.2f}")

    logger.info("\nExpected Results:")
    logger.info("  Success rate: 90-95%")
    if config['limit']:
        runtime_estimate = (config['limit'] * 6) / 60  # ~6 seconds per practice
        logger.info(f"  Runtime: ~{runtime_estimate:.1f} minutes")
    else:
        logger.info("  Runtime: 3-5 hours")

    logger.info("\n" + "="*80)
    logger.info("STARTING ENRICHMENT")
    logger.info("="*80 + "\n")

    try:
        # Initialize orchestrator
        orchestrator = EnrichmentOrchestrator(
            openrouter_api_key=config['api_key'],
            input_file=config['input_file'],
            output_file=config['output_file'],
            markdown_dir=config['markdown_dir'],
            progress_file=config['progress_file'],
            max_workers=config['max_workers'],
            checkpoint_interval=config['checkpoint_interval'],
            use_pooled_first=config['use_pooled_first'],
            resume=config['resume'],
            limit=config['limit']
        )

        # Run enrichment
        stats = await orchestrator.run()

        logger.info("\n" + "="*80)
        logger.info("ENRICHMENT COMPLETE!")
        logger.info("="*80)
        logger.info(f"\nTotal Practices: {stats['total_practices']}")
        logger.info(f"Successful: {stats['successful']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info(f"Success Rate: {stats['success_rate']}")
        logger.info(f"Total Cost: {stats['total_cost']}")
        logger.info(f"Total Time: {stats['total_time']}")
        logger.info(f"\nResults saved to: {OUTPUT_FILE}")
        logger.info(f"Progress saved to: {PROGRESS_FILE}")

    except KeyboardInterrupt:
        logger.warning("\n" + "="*80)
        logger.warning("ENRICHMENT INTERRUPTED BY USER")
        logger.warning("="*80)
        logger.info("\nProgress has been saved. You can resume by running this script again.")

    except Exception as e:
        logger.error("\n" + "="*80)
        logger.error("ENRICHMENT FAILED")
        logger.error("="*80)
        logger.error(f"\nError: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(main())
