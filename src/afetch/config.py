"""Configuration settings for afetch."""

from dataclasses import dataclass


@dataclass
class FetcherConfig:
    """Configuration for afetch.

    Attributes:
        rate_limit_per_domain: Maximum requests per domain per time period.
        rate_limit_period: Time period in seconds for rate limiting.
        retry_attempts: Number of retry attempts for failed requests.
        retry_delay: Base delay in seconds between retry attempts.
        cache_enabled: Whether to enable response caching.

    """

    max_rate_per_domain: int = 1
    time_period_per_domain: float = 1
    retry_attempts: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = True
