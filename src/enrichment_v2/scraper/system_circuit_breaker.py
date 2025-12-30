"""
System-wide circuit breaker for resource exhaustion protection.

Prevents system crashes by blocking new tasks when resources are critically low.
Implements the Circuit Breaker pattern at the system resource level.
"""

import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SystemCircuitBreaker:
    """
    Circuit breaker that opens when system resources are exhausted.

    States:
    - CLOSED: Normal operation (resources healthy)
    - OPEN: Resource exhaustion detected (block new tasks)
    - RECOVERING: Testing if resources have recovered

    Based on observations from production:
    - Thread count >150: pthread_create failures imminent
    - Memory >3GB: SIGSEGV crashes likely
    - CPU >80%: System becoming unresponsive

    The breaker opens after 3 consecutive resource warnings to prevent:
    - BlockingIOError: [Errno 11] Resource temporarily unavailable
    - Worker exited prematurely: signal 11 (SIGSEGV)
    - 50+ minute hangs on stuck practices
    """

    def __init__(self, monitor=None):
        """
        Initialize system circuit breaker.

        Args:
            monitor: ResourceMonitor instance (optional, will create if None)
        """
        # Lazy import to avoid circular dependencies
        if monitor is None:
            from ..utils.resource_monitor import ResourceMonitor
            monitor = ResourceMonitor()

        self.monitor = monitor
        self.state = 'CLOSED'
        self.failure_count = 0
        self.last_failure_time = None
        self.recovery_timeout = 120  # Wait 2 minutes before attempting recovery

    def check_resources_before_task(self) -> Tuple[bool, str]:
        """
        Check if it's safe to start a new task.

        Returns:
            Tuple of (can_proceed: bool, reason: str)
            - (True, "Resources OK") if healthy
            - (False, "Circuit breaker OPEN...") if blocked
        """
        # If circuit is open, check if we should attempt recovery
        if self.state == 'OPEN':
            if self._should_attempt_recovery():
                self.state = 'RECOVERING'
                logger.info("🔄 System circuit breaker: Attempting recovery...")
            else:
                time_since_failure = time.time() - (self.last_failure_time or time.time())
                wait_time = max(0, int(self.recovery_timeout - time_since_failure))
                return False, f"System circuit breaker OPEN. Resources exhausted. Retry in {wait_time}s"

        # Check resource health
        healthy, reason = self.monitor.is_healthy()

        if not healthy:
            self.failure_count += 1
            self.last_failure_time = time.time()

            # Open circuit after 3 consecutive failures
            if self.failure_count >= 3:
                self.state = 'OPEN'
                logger.error(f"⛔ System circuit breaker OPENED: {reason}")
                logger.error("   New tasks will be skipped for 2 minutes to allow recovery")
                return False, f"System resources critical: {reason}"

            # Warning but allow (not critical yet)
            logger.warning(f"⚠️  Resource warning ({self.failure_count}/3): {reason}")
            return True, f"Resource warning: {reason}"

        # Resources OK - reset failure count
        if self.state == 'RECOVERING':
            logger.info("✅ System circuit breaker: Recovery successful, closing circuit")

        self.failure_count = 0
        self.state = 'CLOSED'
        return True, "Resources OK"

    def _should_attempt_recovery(self) -> bool:
        """
        Check if enough time has passed to attempt recovery.

        Returns:
            True if should try recovery, False otherwise
        """
        if not self.last_failure_time:
            return True

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout

    def log_resources(self):
        """Log current resource usage with health indicator."""
        usage_summary = self.monitor.get_usage_summary()
        health_score = self.monitor.get_health_score()

        # Use emoji indicators for quick visual scanning
        if health_score >= 0.8:
            indicator = "✅"  # Healthy
        elif health_score >= 0.6:
            indicator = "⚠️ "  # Warning
        else:
            indicator = "⛔"  # Critical

        logger.info(f"{indicator} Resources: {usage_summary}")

    def get_state(self) -> str:
        """Get current circuit breaker state."""
        return self.state

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        old_state = self.state
        self.state = 'CLOSED'
        self.failure_count = 0
        self.last_failure_time = None
        logger.info(f"System circuit breaker manually reset: {old_state} → CLOSED")

    def __repr__(self) -> str:
        return (
            f"<SystemCircuitBreaker "
            f"state={self.state} "
            f"failures={self.failure_count}/3>"
        )
