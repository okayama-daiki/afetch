"""Core afetch implementation."""

from __future__ import annotations

import asyncio
import collections
import http
import logging
import typing as t
import urllib.parse as parser

import aiohttp
import aiohttp_retry
import aiolimiter
from aiohttp_client_cache import FileBackend
from aiohttp_client_cache.session import CachedSession
from yarl import URL

from .config import FetcherConfig
from .errors import (
    FetcherError,
    FetcherTimeoutError,
    RequestError,
    ResponseError,
)
from .types import HttpMethod, RequestOptions, ResponseType

if t.TYPE_CHECKING:
    from types import TracebackType

# Module-level logger for structured logging
_logger = logging.getLogger("afetch")

# Type alias for response types
ResponseResult = str | dict[str, t.Any] | list[t.Any] | bytes | aiohttp.ClientResponse


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
        self._cache_backend = self.config.cache_backend or FileBackend(
            cache_name=".afetch_cache",
        )
        if not self.config.cache_enabled:
            self._cache_backend.expire_after = 0
        self._limiters: dict[str, aiolimiter.AsyncLimiter] = collections.defaultdict(
            lambda: aiolimiter.AsyncLimiter(
                max_rate=self.config.max_rate_per_domain,
                time_period=self.config.time_period_per_domain,
            ),
        )
        self._session: CachedSession | None = None
        self._client: aiohttp_retry.RetryClient | None = None
        self._logger = self.config.logger or _logger

    def _get_domain(self, url: str | URL) -> str:
        """Extract domain from URL for rate limiting.

        Args:
            url: The URL to extract domain from.

        Returns:
            str: The domain (host:port) of the URL. May be empty for invalid URLs.

        Raises:
            ValueError: If the URL object has no domain (None).

        """
        domain = (
            url.host_port_subcomponent
            if isinstance(url, URL)
            else parser.urlparse(url).netloc
        )
        if domain is None:
            msg = f"Invalid URL: {url}"
            raise ValueError(msg)
        return domain

    def _merge_headers(
        self,
        request_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Merge default headers with request-specific headers.

        Request-specific headers take precedence over default headers.

        Args:
            request_headers: Request-specific headers to merge.

        Returns:
            dict[str, str]: Merged headers dictionary.

        """
        merged = dict(self.config.default_headers)
        if request_headers:
            merged.update(request_headers)
        return merged

    def _get_timeout(self, request_timeout: float | None) -> aiohttp.ClientTimeout | None:
        """Get timeout configuration for a request.

        Args:
            request_timeout: Per-request timeout override.

        Returns:
            aiohttp.ClientTimeout or None: Timeout configuration.

        """
        timeout_value = request_timeout if request_timeout is not None else self.config.timeout
        if timeout_value is not None:
            return aiohttp.ClientTimeout(total=timeout_value)
        return None

    async def _handle_response(
        self,
        response: aiohttp.ClientResponse,
        response_type: ResponseType,
    ) -> ResponseResult:
        """Handle response based on response type.

        Args:
            response: The aiohttp response object.
            response_type: How to handle the response.

        Returns:
            Response content in the specified format.

        Raises:
            ResponseError: If response parsing fails.

        """
        url_str = str(response.url)

        if response_type == ResponseType.RAW:
            return response

        if response_type == ResponseType.TEXT:
            return await response.text()

        if response_type == ResponseType.BYTES:
            return await response.read()

        if response_type == ResponseType.JSON:
            try:
                return await response.json()  # pyright: ignore[reportReturnType]
            except Exception as e:
                msg = "Failed to parse JSON response"
                raise ResponseError(
                    msg,
                    cause=e,
                    url=url_str,
                    status=response.status,
                    response=response,
                ) from e

        # Should never reach here, but satisfies type checker
        return await response.text()  # pragma: no cover

    def _build_request_kwargs(
        self,
        options: RequestOptions,
    ) -> dict[str, t.Any]:
        """Build kwargs dict for aiohttp request.

        Args:
            options: Request options.

        Returns:
            dict: Keyword arguments for the request.

        """
        headers = self._merge_headers(options.headers)
        timeout = self._get_timeout(options.timeout)

        kwargs: dict[str, t.Any] = {
            "headers": headers if headers else None,
            "allow_redirects": options.allow_redirects,
        }
        if timeout:
            kwargs["timeout"] = timeout
        if options.data is not None:
            kwargs["data"] = options.data
        if options.json is not None:
            kwargs["json"] = options.json
        if options.params is not None:
            kwargs["params"] = options.params

        return kwargs

    def _get_request_method(
        self,
        method: HttpMethod,
    ) -> t.Callable[..., t.Any]:
        """Get the appropriate request method from the client.

        Args:
            method: HTTP method enum.

        Returns:
            The corresponding client method.

        """
        assert self._client is not None
        method_map = {
            HttpMethod.GET: self._client.get,
            HttpMethod.POST: self._client.post,
            HttpMethod.PUT: self._client.put,
            HttpMethod.DELETE: self._client.delete,
            HttpMethod.PATCH: self._client.patch,
            HttpMethod.HEAD: self._client.head,
            HttpMethod.OPTIONS: self._client.options,
        }
        return method_map[method]

    async def _apply_rate_limit(
        self,
        url: str | URL,
        url_str: str,
        domain: str,
    ) -> None:
        """Apply rate limiting for non-cached requests.

        Args:
            url: The URL being requested.
            url_str: String representation of the URL.
            domain: The domain for rate limiting.

        """
        assert self._session is not None
        cache_hit = await self._session.cache.has_url(url)  # pyright: ignore[reportUnknownMemberType]
        if cache_hit:
            self._logger.debug("Cache hit for URL: %s", url_str)
        else:
            self._logger.debug("Cache miss for URL: %s, applying rate limit", url_str)
            limiter = self._limiters[domain]
            async with limiter:
                self._logger.debug("Rate limit acquired for domain: %s", domain)

    async def request(
        self,
        url: str | URL,
        options: RequestOptions | None = None,
    ) -> ResponseResult:
        """Make an HTTP request with full control over method and options.

        This method provides a unified API for making HTTP requests with
        arbitrary methods, payloads, and per-request configuration overrides.

        Args:
            url: The URL to make the request to.
            options: Request options for method, headers, body, timeout, etc.

        Returns:
            Response content based on response_type setting.

        Raises:
            RuntimeError: If called outside of an async context manager.
            FetcherError: If the request fails.
            FetcherTimeoutError: If the request times out.
            ResponseError: If response processing fails.

        """
        if not self._session or not self._client:
            msg = "Fetcher must be used as async context manager"
            raise RuntimeError(msg)

        options = options or RequestOptions()
        url_str = str(url)
        domain = self._get_domain(url)

        self._logger.debug("Starting request: %s %s", options.method.value, url_str)
        await self._apply_rate_limit(url, url_str, domain)

        kwargs = self._build_request_kwargs(options)
        request_method = self._get_request_method(options.method)

        try:
            return await self._execute_request(
                request_method,
                url,
                kwargs,
                options,
                url_str,
            )
        except FetcherError:
            raise
        except TimeoutError as e:
            self._logger.warning("Request timeout: %s %s", options.method.value, url_str)
            msg = f"Request timed out: {url_str}"
            raise FetcherTimeoutError(msg, cause=e, url=url_str) from e
        except aiohttp.ClientResponseError as e:
            self._logger.warning("Response error: %s %s -> %d", options.method.value, url_str, e.status)
            msg = f"HTTP error {e.status}: {e.message}"
            raise ResponseError(msg, cause=e, url=url_str, status=e.status) from e
        except aiohttp.ClientError as e:
            self._logger.warning("Request error: %s %s -> %s", options.method.value, url_str, e)
            msg = f"Request failed: {e}"
            raise RequestError(msg, cause=e, url=url_str) from e
        except Exception as e:
            self._logger.warning("Unexpected error: %s %s -> %s", options.method.value, url_str, e)
            msg = f"Unexpected error during request: {e}"
            raise RequestError(msg, cause=e, url=url_str) from e

    async def _execute_request(
        self,
        request_method: t.Callable[..., t.Any],
        url: str | URL,
        kwargs: dict[str, t.Any],
        options: RequestOptions,
        url_str: str,
    ) -> ResponseResult:
        """Execute the HTTP request and handle the response.

        Args:
            request_method: The aiohttp client method to call.
            url: The URL to request.
            kwargs: Request keyword arguments.
            options: Request options.
            url_str: String representation of URL for logging.

        Returns:
            Response content.

        """
        async with request_method(url, **kwargs) as response:
            # Check for non-OK status (HEAD requests with <400 are acceptable)
            is_head_ok = options.method == HttpMethod.HEAD and response.status < 400  # noqa: PLR2004
            if response.status != http.HTTPStatus.OK and not is_head_ok:
                self._logger.warning(
                    "Non-OK response: %s %s -> %d",
                    options.method.value,
                    url_str,
                    response.status,
                )
                response.raise_for_status()

            self._logger.debug(
                "Request completed: %s %s -> %d",
                options.method.value,
                url_str,
                response.status,
            )

            return await self._handle_response(response, options.response_type)

    async def fetch(self, url: str | URL) -> str:
        """Fetch content from a single URL.

        This method applies rate limiting per domain, checks cache first,
        and automatically retries failed requests according to the configuration.
        This is a convenience wrapper around request() that always returns text.

        Args:
            url: The URL to fetch content from.

        Returns:
            str: The text content of the HTTP response.

        Raises:
            RuntimeError: If called outside of an async context manager.
            aiohttp.client_exceptions.InvalidUrlClientError: If the URL is invalid.

        """
        if not self._session or not self._client:
            msg = "Fetcher must be used as async context manager"
            raise RuntimeError(msg)

        domain = self._get_domain(url)

        if not await self._session.cache.has_url(url):  # pyright: ignore[reportUnknownMemberType]
            limiter = self._limiters[domain]
            async with limiter:
                pass

        async with self._client.get(url) as response:
            if response.status != http.HTTPStatus.OK:
                response.raise_for_status()
            return await response.text()

    async def fetch_all(
        self,
        urls: t.Iterable[str | URL],
        options: RequestOptions | None = None,
    ) -> list[ResponseResult | BaseException]:
        """Fetch content from multiple URLs concurrently.

        This method creates concurrent tasks for each URL while still respecting
        rate limiting per domain and cache policies.

        Args:
            urls: An iterable of URLs to fetch content from.
            options: Optional request options to apply to all requests.
                When None, uses legacy fetch() behavior returning text strings.
                When provided, uses request() with the specified options.

        Returns:
            list: A list of responses in the same order as input URLs.
                  When options is None: list of text strings (str).
                  When options is provided: list of ResponseResult based on response_type.
                  If return_exceptions is True, exceptions are included in the list
                  instead of being raised.

        Raises:
            RuntimeError: If called outside of an async context manager.

        """
        if not self._session or not self._client:
            msg = "Fetcher must be used as async context manager"
            raise RuntimeError(msg)

        if options is None:
            # Use legacy behavior for backwards compatibility - returns list[str]
            # Since str is part of ResponseResult union, this is type-safe
            tasks = [self.fetch(url) for url in urls]
            results: list[str] = await asyncio.gather(*tasks)
            return results  # type: ignore[return-value]

        tasks = [self.request(url, options) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=self.config.return_exceptions)  # pyright: ignore[reportReturnType]

    async def __aenter__(self) -> t.Self:
        """Enter the async context manager.

        Initializes the HTTP session with caching and retry client with
        exponential backoff according to the configuration.

        Returns:
            Fetcher: The fetcher instance for use in async with statement.

        """
        self._session = CachedSession(cache=self._cache_backend)
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
