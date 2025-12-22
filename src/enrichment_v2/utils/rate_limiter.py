"""
Rate limiter for domain-based request throttling

Prevents IP bans by limiting concurrent requests per domain.

Features:
- Token bucket algorithm
- Per-domain limits
- Thread-safe with asyncio locks
- Automatic cleanup of inactive domains
"""

import asyncio
import time
from typing import Dict, Optional
from urllib.parse import urlparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.

    Algorithm:
    - Bucket has max capacity of tokens
    - Tokens refill at constant rate
    - Each request consumes one token
    - Request blocks if no tokens available
    """
    capacity: int
    refill_rate: float  # Tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        """Initialize with full bucket"""
        self.tokens = float(self.capacity)
        self.last_refill = time.time()

    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Calculate new tokens
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_time(self, tokens: int = 1) -> float:
        """
        Calculate time to wait for tokens to be available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Seconds to wait (0 if tokens available now)
        """
        self._refill()

        if self.tokens >= tokens:
            return 0.0

        # Calculate how long until we have enough tokens
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """
    Domain-based rate limiter using token bucket algorithm.

    Thread-safe for async operations.
    Automatically creates buckets for new domains.
    Cleans up inactive domains to prevent memory leaks.

    Example:
        limiter = RateLimiter(max_concurrent=5, delay=1.0)
        async with limiter.limit("example.com"):
            # Make request to example.com
            response = await fetch(url)
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        delay: float = 1.0,
        cleanup_interval: int = 300,  # 5 minutes
    ):
        """
        Initialize rate limiter.

        Args:
            max_concurrent: Max concurrent requests per domain
            delay: Minimum seconds between requests (per domain)
            cleanup_interval: Seconds between cleanup of inactive domains
        """
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.cleanup_interval = cleanup_interval

        # Token buckets per domain
        self._buckets: Dict[str, TokenBucket] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._last_access: Dict[str, datetime] = {}

        # Global lock for bucket creation
        self._global_lock = asyncio.Lock()

        # Start cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None

    async def _get_bucket(self, domain: str) -> TokenBucket:
        """
        Get or create token bucket for domain.

        Args:
            domain: Domain name

        Returns:
            TokenBucket for this domain
        """
        if domain not in self._buckets:
            async with self._global_lock:
                # Double-check after acquiring lock
                if domain not in self._buckets:
                    self._buckets[domain] = TokenBucket(
                        capacity=self.max_concurrent,
                        refill_rate=1.0 / self.delay
                    )
                    self._locks[domain] = asyncio.Lock()
                    logger.debug(f"Created rate limiter bucket for {domain}")

        self._last_access[domain] = datetime.now()
        return self._buckets[domain]

    async def acquire(self, url: str):
        """
        Acquire permission to make request to URL.

        Blocks until rate limit allows the request.

        Args:
            url: Full URL or domain name
        """
        domain = self._extract_domain(url)
        bucket = await self._get_bucket(domain)

        # Get lock for this domain
        lock = self._locks[domain]

        async with lock:
            # Wait if necessary
            wait_time = bucket.wait_time(tokens=1)
            if wait_time > 0:
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s for {domain}")
                await asyncio.sleep(wait_time)

            # Consume token
            while not bucket.consume(tokens=1):
                await asyncio.sleep(0.1)  # Small sleep and retry

    def limit(self, url: str):
        """
        Context manager for rate limiting.

        Usage:
            async with limiter.limit("https://example.com/page"):
                response = await fetch(url)

        Args:
            url: Full URL or domain name

        Returns:
            Async context manager
        """
        return _RateLimitContext(self, url)

    @staticmethod
    def _extract_domain(url: str) -> str:
        """
        Extract domain from URL.

        Args:
            url: Full URL or domain name

        Returns:
            Domain name
        """
        # If not a URL, assume it's already a domain
        if not url.startswith(('http://', 'https://')):
            return url

        parsed = urlparse(url)
        return parsed.netloc or parsed.path

    async def _cleanup_inactive(self):
        """Remove buckets for inactive domains (internal use)"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                async with self._global_lock:
                    cutoff = datetime.now() - timedelta(seconds=self.cleanup_interval)
                    inactive = [
                        domain for domain, last_access in self._last_access.items()
                        if last_access < cutoff
                    ]

                    for domain in inactive:
                        del self._buckets[domain]
                        del self._locks[domain]
                        del self._last_access[domain]

                    if inactive:
                        logger.debug(f"Cleaned up {len(inactive)} inactive rate limiter buckets")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {e}")

    def start_cleanup(self):
        """Start background cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_inactive())

    async def stop_cleanup(self):
        """Stop background cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def get_stats(self) -> Dict[str, dict]:
        """
        Get statistics for all domains.

        Returns:
            Dict mapping domain to stats
        """
        return {
            domain: {
                'tokens_available': bucket.tokens,
                'capacity': bucket.capacity,
                'refill_rate': bucket.refill_rate,
                'last_access': self._last_access.get(domain),
            }
            for domain, bucket in self._buckets.items()
        }

    def __repr__(self) -> str:
        return (
            f"<RateLimiter max_concurrent={self.max_concurrent} "
            f"delay={self.delay}s domains={len(self._buckets)}>"
        )


class _RateLimitContext:
    """Context manager for rate limiting (internal use)"""

    def __init__(self, limiter: RateLimiter, url: str):
        self.limiter = limiter
        self.url = url

    async def __aenter__(self):
        """Acquire rate limit on enter"""
        await self.limiter.acquire(self.url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No action needed on exit"""
        pass
