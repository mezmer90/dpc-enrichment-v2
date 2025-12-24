"""
API Pause/Resume Handler

Handles pausing enrichment when APIs fail due to budget/rate limits
and allows user to refresh credentials and resume.
"""

import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class APIPauseHandler:
    """
    Manages pausing and resuming enrichment when API issues occur.

    When an API budget or rate limit error is detected:
    1. Pause the enrichment process
    2. Show clear message to user about the issue
    3. Ask user to refresh API credits/wait for rate limit reset
    4. Allow user to resume when ready
    """

    def __init__(self):
        self.paused = False
        self.pause_reason = None
        self.api_name = None
        self.pause_time = None

    def should_pause(self) -> bool:
        """Check if enrichment should be paused"""
        return self.paused

    def pause_for_api_issue(
        self,
        api_name: str,
        error_type: str,
        error_message: str,
        retry_after: Optional[int] = None
    ):
        """
        Pause enrichment due to API issue.

        Args:
            api_name: Name of the API ('OpenRouter', 'ScraperAPI')
            error_type: Type of error ('budget', 'rate_limit')
            error_message: Detailed error message
            retry_after: Seconds to wait (for rate limits)
        """
        self.paused = True
        self.pause_reason = error_type
        self.api_name = api_name
        self.pause_time = datetime.now()

        logger.error("=" * 80)
        logger.error("ENRICHMENT PAUSED - API ISSUE DETECTED")
        logger.error("=" * 80)
        logger.error(f"API: {api_name}")
        logger.error(f"Issue: {error_type.upper()}")
        logger.error(f"Error: {error_message}")

        if error_type == 'budget':
            logger.error("\n[!] API BUDGET/CREDITS EXHAUSTED")
            logger.error("\nAction required:")
            logger.error(f"1. Go to {api_name} dashboard")
            logger.error("2. Add more credits/upgrade your plan")
            logger.error("3. Verify your new balance is sufficient")
            logger.error("4. Press Enter to resume enrichment")

        elif error_type == 'rate_limit':
            logger.error("\n[!] API RATE LIMIT HIT")
            if retry_after:
                logger.error(f"\nWait time: {retry_after} seconds (~{retry_after // 60} minutes)")
                logger.error(f"You can resume after: {datetime.now().timestamp() + retry_after}")
            logger.error("\nAction required:")
            logger.error("1. Wait for rate limit to reset")
            logger.error(f"2. OR upgrade your {api_name} plan for higher limits")
            logger.error("3. Press Enter when ready to resume")

        logger.error("\n" + "=" * 80)
        logger.error("IMPORTANT: Data is safe - all progress has been saved!")
        logger.error("=" * 80)

    def prompt_user_to_resume(self) -> bool:
        """
        Prompt user to resume enrichment.

        Returns:
            True if user wants to resume, False to abort
        """
        try:
            logger.info("\n" + "=" * 80)
            logger.info("PAUSED - Waiting for user action")
            logger.info("=" * 80)
            logger.info("\nOptions:")
            logger.info("  1. Press Enter to RESUME enrichment")
            logger.info("  2. Press Ctrl+C to STOP and exit")
            logger.info("\nEnrichment will resume from where it paused.")
            logger.info("No practices will be marked as failed due to API issues.\n")

            # Wait for user input
            input("Press Enter when ready to resume... ")

            logger.info("\n[OK] Resuming enrichment...")
            logger.info("Testing API connection before proceeding...")

            return True

        except KeyboardInterrupt:
            logger.warning("\n\n[!] User chose to stop enrichment")
            logger.info("Progress has been saved. You can resume later by running the script again.")
            return False

    def resume(self):
        """Resume enrichment after user intervention"""
        logger.info("=" * 80)
        logger.info("RESUMING ENRICHMENT")
        logger.info("=" * 80)
        pause_duration = (datetime.now() - self.pause_time).total_seconds()
        logger.info(f"Paused for: {pause_duration:.1f} seconds (~{pause_duration / 60:.1f} minutes)")
        logger.info(f"Reason: {self.pause_reason} error on {self.api_name}")
        logger.info("=" * 80)

        self.paused = False
        self.pause_reason = None
        self.api_name = None
        self.pause_time = None

    def get_status(self) -> Dict:
        """Get current pause status"""
        return {
            'paused': self.paused,
            'reason': self.pause_reason,
            'api': self.api_name,
            'pause_time': self.pause_time.isoformat() if self.pause_time else None,
            'duration_seconds': (datetime.now() - self.pause_time).total_seconds() if self.pause_time else 0
        }
