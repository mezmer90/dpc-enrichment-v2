"""
Circuit Breaker pattern implementation

Prevents repeated attempts to scrape failing domains,
improving overall system resilience and performance.

States:
- CLOSED: Normal operation, requests go through
- OPEN: Too many failures, requests blocked
- HALF_OPEN: Testing if service recovered
"""

from enum import Enum
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Statistics for a circuit"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_change_time: datetime = None

    def __post_init__(self):
        if self.state_change_time is None:
            self.state_change_time = datetime.now()

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate (0.0 to 1.0)"""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests


class CircuitBreaker:
    """
    Circuit breaker for domain-level failure protection.

    Uses the Circuit Breaker pattern to prevent cascading failures
    and unnecessary retries to consistently failing domains.

    Thread-safe implementation using locks.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: Optional[str] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery (half-open)
            expected_exception: Exception type to catch
            name: Optional name for this circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name or "CircuitBreaker"

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (thread-safe)"""
        with self._lock:
            return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics (thread-safe copy)"""
        with self._lock:
            return CircuitStats(
                total_requests=self._stats.total_requests,
                successful_requests=self._stats.successful_requests,
                failed_requests=self._stats.failed_requests,
                last_failure_time=self._stats.last_failure_time,
                last_success_time=self._stats.last_success_time,
                state_change_time=self._stats.state_change_time,
            )

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func execution

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If func raises an exception
        """
        with self._lock:
            self._stats.total_requests += 1

            # Check if circuit is open
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._change_state(CircuitState.HALF_OPEN)
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )

        # Execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute async function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func execution

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If func raises an exception
        """
        with self._lock:
            self._stats.total_requests += 1

            # Check if circuit is open
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._change_state(CircuitState.HALF_OPEN)
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )

        # Execute the async function
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        if self._stats.last_failure_time is None:
            return True

        time_since_failure = datetime.now() - self._stats.last_failure_time
        return time_since_failure > timedelta(seconds=self.recovery_timeout)

    def _on_success(self):
        """Handle successful execution"""
        with self._lock:
            self._stats.successful_requests += 1
            self._stats.last_success_time = datetime.now()

            # Reset circuit if in HALF_OPEN state
            if self._state == CircuitState.HALF_OPEN:
                self._change_state(CircuitState.CLOSED)
                self._stats.failed_requests = 0  # Reset failure count

    def _on_failure(self):
        """Handle failed execution"""
        with self._lock:
            self._stats.failed_requests += 1
            self._stats.last_failure_time = datetime.now()

            # Open circuit if threshold exceeded
            if self._stats.failed_requests >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._change_state(CircuitState.OPEN)

    def _change_state(self, new_state: CircuitState):
        """Change circuit state (assumes lock is held)"""
        old_state = self._state
        self._state = new_state
        self._stats.state_change_time = datetime.now()

        print(f"[{self.name}] Circuit state changed: {old_state.value} → {new_state.value}")

    def reset(self):
        """Manually reset circuit to CLOSED state"""
        with self._lock:
            self._change_state(CircuitState.CLOSED)
            self._stats.failed_requests = 0

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker name='{self.name}' "
            f"state={self._state.value} "
            f"failures={self._stats.failed_requests}/{self.failure_threshold}>"
        )


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers (e.g., one per domain).

    Thread-safe singleton pattern for global circuit breaker management.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Implement singleton pattern"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._breakers = {}
                cls._instance._breakers_lock = threading.RLock()
            return cls._instance

    def get_breaker(
        self,
        key: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60
    ) -> CircuitBreaker:
        """
        Get or create circuit breaker for a key (e.g., domain name).

        Args:
            key: Unique identifier (e.g., domain name)
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery

        Returns:
            CircuitBreaker instance for this key
        """
        with self._breakers_lock:
            if key not in self._breakers:
                self._breakers[key] = CircuitBreaker(
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    name=key
                )
            return self._breakers[key]

    def get_stats(self) -> Dict[str, CircuitStats]:
        """Get statistics for all circuit breakers"""
        with self._breakers_lock:
            return {
                key: breaker.stats
                for key, breaker in self._breakers.items()
            }

    def reset_all(self):
        """Reset all circuit breakers"""
        with self._breakers_lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def get_open_breakers(self) -> list[str]:
        """Get list of keys with open circuit breakers"""
        with self._breakers_lock:
            return [
                key for key, breaker in self._breakers.items()
                if breaker.state == CircuitState.OPEN
            ]

    def __repr__(self) -> str:
        with self._breakers_lock:
            open_count = len(self.get_open_breakers())
            return f"<CircuitBreakerManager circuits={len(self._breakers)} open={open_count}>"
