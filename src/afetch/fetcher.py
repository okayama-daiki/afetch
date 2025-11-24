"""Core afetch implementation."""

import asyncio
import collections
import typing as t
import urllib.parse as parser

import aiohttp_retry
import aiolimiter
from aiohttp_client_cache.session import CachedSession
from yarl import URL

from .config import FetcherConfig

if t.TYPE_CHECKING:
    from types import TracebackType


class Fetcher:
    """Asynchronous HTTP fetcher with rate limiting, retries, and caching.

    This class provides a high-level interface for making HTTP requests with
    built-in rate limiting per domain, automatic retries, and response caching.
    It must be used as an async context manager.

    Attributes:
        config: Configuration object containing rate limiting, retry, and caching settings.

    """

    def __init__(self, config: FetcherConfig | None = None) -> None:
        """Initialize the Fetcher with configuration settings.

        Args:
            config: Configuration object for the fetcher. If None, uses default
                   configuration with sensible defaults for rate limiting, retries,
                   and caching.

        """
        self.config = config or FetcherConfig()
        self._limiters: dict[str, aiolimiter.AsyncLimiter] = collections.defaultdict(
            lambda: aiolimiter.AsyncLimiter(
                max_rate=self.config.rate_limit_per_domain,
                time_period=self.config.rate_limit_period,
            ),
        )
        self._session: CachedSession | None = None
        self._client: aiohttp_retry.RetryClient | None = None

    async def fetch(self, url: str | URL) -> str:
        """Fetch content from a single URL.

        This method applies rate limiting per domain, checks cache first,
        and automatically retries failed requests according to the configuration.

        Args:
            url: The URL to fetch content from.

        Returns:
            str: The text content of the HTTP response.

        Raises:
            RuntimeError: If called outside of an async context manager.

        """
        if not self._session or not self._client:
            msg = "Fetcher must be used as async context manager"
            raise RuntimeError(msg)

        domain = url.host if isinstance(url, URL) else parser.urlparse(url).netloc
        if domain is None:
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)

        if not await self._session.cache.has_url(url):  # pyright: ignore[reportUnknownMemberType]
            limiter = self._limiters[domain]
            async with limiter:
                pass
        async with self._client.get(url) as response:
            return await response.text()

    async def fetch_all(self, urls: t.Iterable[str]) -> list[str]:
        """Fetch content from multiple URLs concurrently.

        This method creates concurrent tasks for each URL while still respecting
        rate limiting per domain and cache policies.

        Args:
            urls: An iterable of URLs to fetch content from.

        Returns:
            list[str]: A list of text contents from the HTTP responses,
                      in the same order as the input URLs.

        Raises:
            RuntimeError: If called outside of an async context manager.

        """
        if not self._session or not self._client:
            msg = "Fetcher must be used as async context manager"
            raise RuntimeError(msg)
        tasks = [self.fetch(url) for url in urls]
        return await asyncio.gather(*tasks)

    async def __aenter__(self) -> t.Self:
        """Enter the async context manager.

        Initializes the HTTP session with caching and retry client with
        exponential backoff according to the configuration.

        Returns:
            Fetcher: The fetcher instance for use in async with statement.

        """
        self._session = CachedSession()
        retry_options = aiohttp_retry.ExponentialRetry(
            attempts=self.config.retry_attempts,
        )
        self._client = aiohttp_retry.RetryClient(
            self._session,
            retry_options=retry_options,
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context manager.

        Properly closes the HTTP session and cleans up resources.

        Args:
            exc_type: Exception type if an exception was raised, None otherwise.
            exc_val: Exception value if an exception was raised, None otherwise.
            exc_tb: Exception traceback if an exception was raised, None otherwise.

        """
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
