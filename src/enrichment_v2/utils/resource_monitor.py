"""
System resource monitoring for circuit breaker protection.

Monitors CPU, memory, threads, processes, and open files to prevent
resource exhaustion that leads to SIGSEGV crashes and system hangs.
"""

import psutil
import os
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    Monitor system resources to prevent exhaustion.

    Tracks:
    - CPU usage (%)
    - Memory usage (% and MB)
    - Thread count
    - Child process count
    - Open file descriptors

    Uses conservative thresholds to prevent crashes observed in production:
    - Thread explosions (pthread_create failures)
    - Memory exhaustion
    - Process limit hits (RLIMIT_NPROC)
    """

    def __init__(self, thresholds: Dict[str, float] = None):
        """
        Initialize resource monitor.

        Args:
            thresholds: Optional custom thresholds dict.
                       Defaults to safe production values.
        """
        try:
            self.process = psutil.Process(os.getpid())
        except Exception as e:
            logger.warning(f"Failed to initialize psutil Process: {e}")
            self.process = None

        # Safe thresholds (conservative based on observed failures)
        self.thresholds = thresholds or {
            'cpu_percent': 80,           # Max 80% CPU
            'memory_percent': 80,        # Max 80% system RAM
            'memory_mb': 3000,           # Max 3GB per process
            'num_threads': 150,          # Max 150 threads (was hitting 500+)
            'num_children': 100,         # Max 100 child processes (browsers spawn 20-30 helpers each)
            'open_files': 400            # Max 400 open files
        }

    def get_current_usage(self) -> Dict[str, float]:
        """
        Get current resource usage metrics.

        Returns:
            Dict with current usage values for each metric
        """
        try:
            usage = {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
            }

            if self.process:
                try:
                    usage['memory_mb'] = self.process.memory_info().rss / 1024 / 1024
                    usage['num_threads'] = self.process.num_threads()

                    # Count child processes
                    children = self.process.children(recursive=True)
                    usage['num_children'] = len(children)

                    # Count open files (may not be available on all systems)
                    try:
                        usage['open_files'] = len(self.process.open_files())
                    except (AttributeError, psutil.AccessDenied):
                        usage['open_files'] = 0

                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    logger.warning(f"Process metrics unavailable: {e}")

            return usage

        except Exception as e:
            logger.warning(f"Failed to get resource usage: {e}")
            return {
                'cpu_percent': 0,
                'memory_percent': 0,
                'memory_mb': 0,
                'num_threads': 0,
                'num_children': 0,
                'open_files': 0
            }

    def is_healthy(self) -> Tuple[bool, str]:
        """
        Check if system resources are within safe limits.

        Returns:
            Tuple of (is_healthy: bool, reason: str)
            - (True, "All resources within limits") if healthy
            - (False, "metric_name exceeded: current > limit") if unhealthy
        """
        usage = self.get_current_usage()

        for metric, limit in self.thresholds.items():
            current = usage.get(metric, 0)
            if current > limit:
                return False, f"{metric} exceeded: {current:.1f} > {limit}"

        return True, "All resources within limits"

    def get_health_score(self) -> float:
        """
        Get overall health score from 0.0 (critical) to 1.0 (perfect).

        Returns:
            Float between 0.0 and 1.0 representing system health
        """
        usage = self.get_current_usage()
        scores = []

        for metric, limit in self.thresholds.items():
            current = usage.get(metric, 0)
            # Score: 1.0 when at 0%, 0.0 when at/above limit
            score = max(0.0, min(1.0, 1.0 - (current / limit)))
            scores.append(score)

        return sum(scores) / len(scores) if scores else 1.0

    def get_usage_summary(self) -> str:
        """
        Get human-readable summary of current resource usage.

        Returns:
            Formatted string with key metrics
        """
        usage = self.get_current_usage()
        health = self.get_health_score()

        return (
            f"CPU={usage.get('cpu_percent', 0):.1f}%, "
            f"RAM={usage.get('memory_percent', 0):.1f}%, "
            f"MEM={usage.get('memory_mb', 0):.0f}MB, "
            f"Threads={usage.get('num_threads', 0)}, "
            f"Children={usage.get('num_children', 0)}, "
            f"Files={usage.get('open_files', 0)}, "
            f"Health={health:.2f}"
        )

    def log_current_usage(self, level: str = 'INFO'):
        """
        Log current resource usage at specified level.

        Args:
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        """
        summary = self.get_usage_summary()

        log_func = {
            'DEBUG': logger.debug,
            'INFO': logger.info,
            'WARNING': logger.warning,
            'ERROR': logger.error
        }.get(level, logger.info)

        log_func(f"Resources: {summary}")

    def check_critical_metrics(self) -> Tuple[bool, list]:
        """
        Check for critically high metrics that require immediate action.

        A metric is critical if it exceeds 95% of its threshold.

        Returns:
            Tuple of (has_critical: bool, critical_metrics: list)
        """
        usage = self.get_current_usage()
        critical_metrics = []

        for metric, limit in self.thresholds.items():
            current = usage.get(metric, 0)
            if current > (limit * 0.95):  # 95% of threshold
                critical_metrics.append(
                    f"{metric}={current:.1f} (limit={limit})"
                )

        return len(critical_metrics) > 0, critical_metrics
