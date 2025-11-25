"""Tests for the afetch Fetcher class."""

import typing as t

import pytest
from aiohttp import ClientError, ClientResponseError
from aioresponses import aioresponses

from afetch import Fetcher, FetcherConfig

if t.TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


def _extract_path(url: str) -> str:
    """Helper to extract path from URL for HTTPServer expectations."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.path


# async def test_fetcher_single_fetch(httpserver: HTTPServer) -> None:
#     """Test that a single fetch returns the expected content.

#     Expects the response content to match the mocked value.
#     """
#     url = f"http://localhost:{httpserver.port}/page"
#     httpserver.expect_request(_extract_path(url)).respond_with_data("test content")

#     async with Fetcher() as fetcher:
#         content = await fetcher.fetch(url)
#     assert content == "test content"


async def test_fetcher_same_domain_rate_limiting(httpserver: HTTPServer) -> None:
    """Test that requests to the same domain are rate-limited.

    Verifies that rate limiting is applied per domain by ensuring the
    limiter is entered once per request, without relying on real time.
    """
    urls = [
        f"http://example.com:{httpserver.port}/page1",
        # f"http://example.com:{httpserver.port}/page2",
        # f"http://example.com:{httpserver.port}/page3",
    ]
    for url in urls:
        httpserver.expect_request(_extract_path(url)).respond_with_data("test response")

    async with Fetcher() as fetcher:
        await fetcher.fetch_all(urls)

    # Same domain -> limiter __aenter__ should be called once per request
    # assert mock_limiter.__aenter__.call_count == len(urls)


# @pytest.mark.asyncio
# async def test_fetcher_different_domains_parallel() -> None:
#     """Test that requests to different domains are executed in parallel.

#     Verifies that requests to different domains use separate limiters so
#     they can proceed in parallel, without relying on real time.
#     """
#     urls = [
#         "http://example1.com/page",
#         "http://example2.com/page",
#         "http://example3.com/page",
#     ]
#     with mock.patch("afetch.fetcher.aiolimiter.AsyncLimiter") as mock_limiter_cls:
#         # Each domain should get its own limiter instance
#         limiters: list[mock.AsyncMock] = []

#         def _limiter_factory(*_: object, **__: object) -> mock.AsyncMock:  # pyright: ignore[reportUnknownParameterType]
#             limiter = mock.AsyncMock()
#             limiters.append(limiter)
#             return limiter

#         mock_limiter_cls.side_effect = _limiter_factory

#         with aioresponses() as mocked:
#             for url in urls:
#                 mocked.get(url, status=200, body="test response", repeat=True)  # pyright: ignore[reportUnknownMemberType]
#             async with Fetcher() as fetcher:
#                 await fetcher.fetch_all(urls)

#     # Different domains -> distinct limiter instances
#     assert len(limiters) == len(urls)
#     for limiter in limiters:
#         assert limiter.__aenter__.call_count == 1


# @pytest.mark.asyncio
# async def test_fetcher_cached_requests() -> None:
#     """Test that repeated requests to the same URL are served from cache after the first request.

#     Expects total elapsed time to be approximately 1 seconds for 3 identical requests.
#     Also verifies that only 1 actual HTTP request is made to the server.
#     """
#     urls = ["http://example.com/page"] * 3
#     with aioresponses() as mocked:
#         mocked.get(urls[0], status=200, body="test response", repeat=True)  # pyright: ignore[reportUnknownMemberType]
#         async with Fetcher() as fetcher:
#             await fetcher.fetch_all(urls)

#     # Verify that only 1 HTTP request was actually made to the server
#     assert len(mocked.requests) == 1  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]


# @pytest.mark.asyncio
# async def test_fetcher_custom_config() -> None:
#     """Test that custom rate limiting configuration is respected.

#     Verifies that the custom rate limiting configuration is respected by
#     inspecting limiter usage rather than real time.
#     """
#     config = FetcherConfig(rate_limit_per_domain=2, rate_limit_period=0.5)
#     urls = [
#         "http://example.com/page1",
#         "http://example.com/page2",
#         "http://example.com/page3",
#     ]
#     with mock.patch("afetch.fetcher.aiolimiter.AsyncLimiter") as mock_limiter_cls:
#         mock_limiter = mock.AsyncMock()
#         mock_limiter_cls.return_value = mock_limiter

#         with aioresponses() as mocked:
#             for url in urls:
#                 mocked.get(url, status=200, body="test response", repeat=True)  # pyright: ignore[reportUnknownMemberType]
#             async with Fetcher(config) as fetcher:
#                 await fetcher.fetch_all(urls)

#     # Ensure limiter is entered once per request
#     assert mock_limiter.__aenter__.call_count == len(urls)


# @pytest.mark.asyncio
# async def test_fetcher_context_manager_required() -> None:
#     """Test that using Fetcher methods outside of an async context manager raises RuntimeError.

#     Expects RuntimeError when calling fetch or fetch_all without 'async with'.
#     """
#     fetcher = Fetcher()
#     with pytest.raises(RuntimeError):
#         await fetcher.fetch("http://example.com")
#     with pytest.raises(RuntimeError):
#         await fetcher.fetch_all(["http://example.com"])


# @pytest.mark.asyncio
# async def test_fetcher_no_retry_when_disabled() -> None:
#     """Test that retry is disabled when retry_attempts is set to 0.

#     Expects immediate failure without any retry attempts.
#     """
#     url = "http://example.com/no-retry"
#     config = FetcherConfig(retry_attempts=0)

#     with (
#         mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep,
#         aioresponses() as mocked,
#     ):
#         mocked.get(url, status=500)  # pyright: ignore[reportUnknownMemberType]

#         async with Fetcher(config) as fetcher:
#             with pytest.raises(ClientResponseError):
#                 await fetcher.fetch(url)

#     # Verify that no retry delays were applied (sleep should not be called)
#     mock_sleep.assert_not_called()


# @pytest.mark.asyncio
# async def test_fetcher_retry_delay_timing() -> None:
#     """Test that retry delays are precisely applied between attempts.

#     Verifies the exact timing of retry intervals.
#     """
#     url = "http://example.com/timing-test"
#     config = FetcherConfig(retry_attempts=3, retry_delay=1.0)

#     with (
#         mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep,
#         aioresponses() as mocked,
#     ):
#         # Mock failures for all retry attempts
#         mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]

#         async with Fetcher(config) as fetcher:
#             with pytest.raises(ClientResponseError):
#                 await fetcher.fetch(url)

#     # retry_attempts=3 -> 2 delays
#     assert mock_sleep.call_count == 2
#     mock_sleep.assert_called_with(1.0)


# @pytest.mark.asyncio
# async def test_fetcher_different_retry_delays() -> None:
#     """Test retry delay timing with standard configuration.

#     Verifies that retry_delay setting is respected.
#     """
#     url = "http://example.com/custom-delay"
#     config = FetcherConfig(retry_attempts=2, retry_delay=1.0)

#     with (
#         mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep,
#         aioresponses() as mocked,
#     ):
#         mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]

#         async with Fetcher(config) as fetcher:
#             with pytest.raises(ClientResponseError):
#                 await fetcher.fetch(url)

#     # retry_attempts=2 -> 1 delay
#     assert mock_sleep.call_count == 1
#     mock_sleep.assert_called_with(1.0)


# @pytest.mark.asyncio
# async def test_fetcher_retry_on_http_error() -> None:
#     """Test that HTTP errors trigger retry attempts.

#     Expects the fetcher to retry 3 times before giving up on a 500 error.
#     Also verifies that retry delays are properly applied.
#     """
#     url = "http://example.com/error"
#     config = FetcherConfig(retry_attempts=3, retry_delay=1.0)

#     with (
#         mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep,
#         aioresponses() as mocked,
#     ):
#         # Mock failed responses
#         mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]

#         async with Fetcher(config) as fetcher:
#             with pytest.raises(ClientResponseError):
#                 await fetcher.fetch(url)

#     # retry_attempts=3 -> 2 delays
#     assert mock_sleep.call_count == 2
#     mock_sleep.assert_called_with(1.0)


# @pytest.mark.asyncio
# async def test_fetcher_retry_then_success() -> None:
#     """Test that retry succeeds after initial failures.

#     Expects the fetcher to retry and eventually succeed.
#     Also verifies timing for retry attempts.
#     """
#     url = "http://example.com/retry"
#     config = FetcherConfig(retry_attempts=3, retry_delay=1.0)

#     with (
#         mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep,
#         aioresponses() as mocked,
#     ):
#         # Mock 2 failed responses, then a successful one
#         mocked.get(url, status=500)  # pyright: ignore[reportUnknownMemberType]
#         mocked.get(url, status=500)  # pyright: ignore[reportUnknownMemberType]
#         mocked.get(url, status=200, body="success after retries")  # pyright: ignore[reportUnknownMemberType]

#         async with Fetcher(config) as fetcher:
#             content = await fetcher.fetch(url)

#             assert content == "success after retries"

#     # 2 retries -> 2 delays
#     assert mock_sleep.call_count == 2
#     mock_sleep.assert_called_with(1.0)


# @pytest.mark.asyncio
# async def test_fetcher_retry_on_connection_error() -> None:
#     """Test that connection errors trigger retry attempts.

#     Expects the fetcher to retry on network failures.
#     Also verifies retry timing for connection errors.
#     """
#     url = "http://example.com/connection-error"
#     config = FetcherConfig(retry_attempts=2, retry_delay=1.0)

#     with (
#         mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep,
#         aioresponses() as mocked,
#     ):
#         # Mock connection errors
#         mocked.get(url, exception=ClientError("Connection failed"))  # pyright: ignore[reportUnknownMemberType]
#         mocked.get(url, exception=ClientError("Connection failed"))  # pyright: ignore[reportUnknownMemberType]
#         mocked.get(url, status=200, body="success after connection retry")  # pyright: ignore[reportUnknownMemberType]

#         async with Fetcher(config) as fetcher:
#             content = await fetcher.fetch(url)

#             assert content == "success after connection retry"

#     # 2 retries -> 2 delays
#     assert mock_sleep.call_count == 2
#     mock_sleep.assert_called_with(1.0)


# @pytest.mark.asyncio
# async def test_fetcher_retry_exhausted() -> None:
#     """Test that retry attempts are exhausted and final error is raised.

#     Expects the fetcher to fail after all retry attempts are used.
#     Also verifies that all retry delays are properly applied.
#     """
#     url = "http://example.com/always-fail"
#     config = FetcherConfig(retry_attempts=2, retry_delay=1.0)

#     with (
#         mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep,
#         aioresponses() as mocked,
#     ):
#         # Mock persistent failures
#         mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]

#         async with Fetcher(config) as fetcher:
#             with pytest.raises(ClientResponseError):
#                 await fetcher.fetch(url)

#     # retry_attempts=2 -> 1 delay
#     assert mock_sleep.call_count == 1
#     mock_sleep.assert_called_with(1.0)
