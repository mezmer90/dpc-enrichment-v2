"""
Retry mechanism with exponential backoff

Implements intelligent retry logic with:
- Exponential backoff: 1s, 2s, 4s, 8s, ...
- Jitter to prevent thundering herd
- Configurable retry conditions
- Type-safe with decorators
"""

import asyncio
import time
import random
from typing import Callable, TypeVar, Optional, Tuple, Type
from dataclasses import dataclass
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on: Tuple[Type[Exception], ...] = (Exception,)

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: delay = base_delay * (exponential_base ^ attempt)
        delay = self.base_delay * (self.exponential_base ** attempt)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter (randomness) to prevent thundering herd
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)  # 50-100% of calculated delay

        return delay


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retrying functions with exponential backoff.

    Supports both sync and async functions.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff (2 = double each time)
        jitter: Add randomness to delays
        retry_on: Tuple of exception types to retry on
        on_retry: Callback function called on each retry

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_attempts=5, base_delay=2.0)
        async def fetch_data(url: str) -> dict:
            response = await client.get(url)
            return response.json()
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retry_on=retry_on,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """Actual decorator"""

        # Check if function is async
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                """Async wrapper with retry logic"""
                last_exception = None

                for attempt in range(config.max_attempts):
                    try:
                        return await func(*args, **kwargs)

                    except config.retry_on as e:
                        last_exception = e

                        # Don't retry on last attempt
                        if attempt == config.max_attempts - 1:
                            logger.warning(
                                f"{func.__name__} failed after {config.max_attempts} attempts"
                            )
                            raise

                        # Calculate delay
                        delay = config.calculate_delay(attempt)

                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                        # Call retry callback if provided
                        if on_retry:
                            on_retry(e, attempt + 1)

                        # Wait before retry
                        await asyncio.sleep(delay)

                # This should never be reached due to raise in loop
                raise last_exception

            return async_wrapper

        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                """Sync wrapper with retry logic"""
                last_exception = None

                for attempt in range(config.max_attempts):
                    try:
                        return func(*args, **kwargs)

                    except config.retry_on as e:
                        last_exception = e

                        # Don't retry on last attempt
                        if attempt == config.max_attempts - 1:
                            logger.warning(
                                f"{func.__name__} failed after {config.max_attempts} attempts"
                            )
                            raise

                        # Calculate delay
                        delay = config.calculate_delay(attempt)

                        logger.warning(
                            f"{func.__name__} attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                        # Call retry callback if provided
                        if on_retry:
                            on_retry(e, attempt + 1)

                        # Wait before retry
                        time.sleep(delay)

                # This should never be reached due to raise in loop
                raise last_exception

            return sync_wrapper

    return decorator


class RetryExhausted(Exception):
    """Raised when all retry attempts are exhausted"""
    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(
            f"Failed after {attempts} attempts. Last error: {last_exception}"
        )


async def retry_async(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> T:
    """
    Retry an async function with given config.

    Alternative to decorator for dynamic retry logic.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        config: RetryConfig instance
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        RetryExhausted: If all attempts fail
    """
    if config is None:
        config = RetryConfig()

    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)

        except config.retry_on as e:
            last_exception = e

            if attempt == config.max_attempts - 1:
                raise RetryExhausted(config.max_attempts, e)

            delay = config.calculate_delay(attempt)
            logger.debug(f"Retry attempt {attempt + 1}/{config.max_attempts} after {delay:.2f}s")
            await asyncio.sleep(delay)

    raise RetryExhausted(config.max_attempts, last_exception)


def retry_sync(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> T:
    """
    Retry a sync function with given config.

    Alternative to decorator for dynamic retry logic.

    Args:
        func: Sync function to retry
        *args: Positional arguments for func
        config: RetryConfig instance
        **kwargs: Keyword arguments for func

    Returns:
        Result of func

    Raises:
        RetryExhausted: If all attempts fail
    """
    if config is None:
        config = RetryConfig()

    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return func(*args, **kwargs)

        except config.retry_on as e:
            last_exception = e

            if attempt == config.max_attempts - 1:
                raise RetryExhausted(config.max_attempts, e)

            delay = config.calculate_delay(attempt)
            logger.debug(f"Retry attempt {attempt + 1}/{config.max_attempts} after {delay:.2f}s")
            time.sleep(delay)

    raise RetryExhausted(config.max_attempts, last_exception)
