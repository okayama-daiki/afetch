"""Configuration settings for afetch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp_client_cache.backends.base import CacheBackend


@dataclass
class FetcherConfig:
    """Configuration for afetch.

    Attributes:
        max_rate_per_domain: Maximum requests per domain per time period.
        time_period_per_domain: Time period in seconds for rate limiting.
        retry_attempts: Number of retry attempts for failed requests.
        cache_backend: Cache backend instance for storing cached responses.
        cache_enabled: Whether caching is enabled, default is True.

    """

    max_rate_per_domain: int = 1
    time_period_per_domain: float = 1
    retry_attempts: int = 3
    cache_backend: CacheBackend | None = None
    cache_enabled: bool = True
