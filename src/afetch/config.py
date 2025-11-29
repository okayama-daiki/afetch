"""Configuration settings for afetch."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .types import ResponseType

if TYPE_CHECKING:
    import logging

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
        default_headers: Default headers to include with every request.
        timeout: Default request timeout in seconds. None means no timeout.
        response_type: Default response handling type.
        logger: Logger instance for structured logging. If None, uses module logger.
        return_exceptions: If True, fetch_all returns exceptions instead of raising.

    """

    max_rate_per_domain: int = 1
    time_period_per_domain: float = 1
    retry_attempts: int = 3
    cache_backend: CacheBackend | None = None
    cache_enabled: bool = True
    default_headers: dict[str, str] = field(default_factory=dict)
    timeout: float | None = None
    response_type: ResponseType = ResponseType.TEXT
    logger: logging.Logger | None = None
    return_exceptions: bool = False
