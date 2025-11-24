"""Tests for the afetch Fetcher class."""

import time
import typing as t
from unittest import mock

import pytest
from aiohttp import ClientError, ClientResponseError
from aioresponses import aioresponses

from afetch import Fetcher, FetcherConfig

if t.TYPE_CHECKING:
    from types import TracebackType

# Timing tolerance constants for test assertions
IMMEDIATE_TIMING_TOLERANCE = 0.1  # For operations that should be immediate
RETRY_TIMING_TOLERANCE = 0.2  # For retry delay timing assertions


class MockEventLoop:
    """Mock event loop to control time for testing purposes."""

    def __init__(self) -> None:
        """Initialize the mock event loop."""
        self.current_time = 0.0
        self.patch = mock.patch("asyncio.get_event_loop", return_value=self)

    def __enter__(self) -> t.Self:
        """Enter the context manager, starting the patch."""
        self.patch.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the context manager, stopping the patch."""
        self.patch.stop()


@pytest.mark.asyncio
async def test_fetcher_single_fetch() -> None:
    """Test that a single fetch returns the expected content.

    Expects the response content to match the mocked value.
    """
    url = "http://example.com/page"
    with aioresponses() as mocked:
        mocked.get(url, status=200, body="test content", repeat=True)  # pyright: ignore[reportUnknownMemberType]
        async with Fetcher() as fetcher:
            content = await fetcher.fetch(url)
    assert content == "test content"


@pytest.mark.asyncio
async def test_fetcher_same_domain_rate_limiting() -> None:
    """Test that requests to the same domain are rate-limited.

    Expects total elapsed time to be approximately 2 seconds for 3 requests (default: 1 req/sec).
    """
    urls = [
        "http://example.com/page1",
        "http://example.com/page2",
        "http://example.com/page3",
    ]
    with aioresponses() as mocked:
        for url in urls:
            mocked.get(url, status=200, body="test response", repeat=True)  # pyright: ignore[reportUnknownMemberType]
        async with Fetcher() as fetcher:
            start = time.time()
            await fetcher.fetch_all(urls)
            elapsed = time.time() - start
    assert elapsed == pytest.approx(2.0, abs=0.1)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_different_domains_parallel() -> None:
    """Test that requests to different domains are executed in parallel.

    Expects total elapsed time to be approximately 0 second for 3 requests to different domains.
    """
    urls = [
        "http://example1.com/page",
        "http://example2.com/page",
        "http://example3.com/page",
    ]
    with aioresponses() as mocked:
        for url in urls:
            mocked.get(url, status=200, body="test response", repeat=True)  # pyright: ignore[reportUnknownMemberType]
        async with Fetcher() as fetcher:
            start = time.time()
            await fetcher.fetch_all(urls)
            elapsed = time.time() - start
    assert elapsed == pytest.approx(0.0, abs=0.1)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_cached_requests() -> None:
    """Test that repeated requests to the same URL are served from cache after the first request.

    Expects total elapsed time to be approximately 1 seconds for 3 identical requests.
    Also verifies that only 1 actual HTTP request is made to the server.
    """
    urls = ["http://example.com/page"] * 3
    with aioresponses() as mocked:
        mocked.get(urls[0], status=200, body="test response", repeat=True)  # pyright: ignore[reportUnknownMemberType]
        async with Fetcher() as fetcher:
            start = time.time()
            await fetcher.fetch_all(urls)
            elapsed = time.time() - start

    # Verify timing (cache should make subsequent requests instant)
    assert elapsed == pytest.approx(1.0, abs=0.1)  # pyright: ignore[reportUnknownMemberType]

    # Verify that only 1 HTTP request was actually made to the server
    assert len(mocked.requests) == 1  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_custom_config() -> None:
    """Test that custom rate limiting configuration is respected.

    Expects total elapsed time to be approximately 0.5 seconds for 3 requests (2 req/0.5 sec).
    """
    config = FetcherConfig(rate_limit_per_domain=2, rate_limit_period=0.5)
    urls = [
        "http://example.com/page1",
        "http://example.com/page2",
        "http://example.com/page3",
    ]
    with aioresponses() as mocked:
        for url in urls:
            mocked.get(url, status=200, body="test response", repeat=True)  # pyright: ignore[reportUnknownMemberType]
        async with Fetcher(config) as fetcher:
            start = time.time()
            await fetcher.fetch_all(urls)
            elapsed = time.time() - start
    assert elapsed == pytest.approx(0.5, abs=0.1)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_context_manager_required() -> None:
    """Test that using Fetcher methods outside of an async context manager raises RuntimeError.

    Expects RuntimeError when calling fetch or fetch_all without 'async with'.
    """
    fetcher = Fetcher()
    with pytest.raises(RuntimeError):
        await fetcher.fetch("http://example.com")
    with pytest.raises(RuntimeError):
        await fetcher.fetch_all(["http://example.com"])


@pytest.mark.asyncio
async def test_fetcher_no_retry_when_disabled() -> None:
    """Test that retry is disabled when retry_attempts is set to 0.

    Expects immediate failure without any retry attempts.
    """
    url = "http://example.com/no-retry"
    config = FetcherConfig(retry_attempts=0)

    with aioresponses() as mocked:
        mocked.get(url, status=500)  # pyright: ignore[reportUnknownMemberType]

        async with Fetcher(config) as fetcher:
            start = time.time()
            with pytest.raises(ClientResponseError):
                await fetcher.fetch(url)
            elapsed = time.time() - start

    # Verify that no retry delays were applied (should fail immediately)
    assert elapsed == pytest.approx(0.0, abs=IMMEDIATE_TIMING_TOLERANCE)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_retry_delay_timing() -> None:
    """Test that retry delays are precisely applied between attempts.

    Verifies the exact timing of retry intervals.
    """
    url = "http://example.com/timing-test"
    config = FetcherConfig(retry_attempts=3, retry_delay=1.0)

    with aioresponses() as mocked:
        # Mock failures for all retry attempts
        mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]

        async with Fetcher(config) as fetcher:
            start = time.time()
            with pytest.raises(ClientResponseError):
                await fetcher.fetch(url)
            elapsed = time.time() - start

    # Verify precise timing: 3 attempts with 2 delays of 1.0s each = ~2.0s
    assert elapsed == pytest.approx(2.0, abs=RETRY_TIMING_TOLERANCE)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_different_retry_delays() -> None:
    """Test retry delay timing with standard configuration.

    Verifies that retry_delay setting is respected.
    """
    url = "http://example.com/custom-delay"
    config = FetcherConfig(retry_attempts=2, retry_delay=1.0)

    with aioresponses() as mocked:
        mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]

        async with Fetcher(config) as fetcher:
            start = time.time()
            with pytest.raises(ClientResponseError):
                await fetcher.fetch(url)
            elapsed = time.time() - start

    # Verify timing: 2 retries x 1.0s = ~2.0s
    assert elapsed == pytest.approx(2.0, abs=RETRY_TIMING_TOLERANCE)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_retry_on_http_error() -> None:
    """Test that HTTP errors trigger retry attempts.

    Expects the fetcher to retry 3 times before giving up on a 500 error.
    Also verifies that retry delays are properly applied.
    """
    url = "http://example.com/error"
    config = FetcherConfig(retry_attempts=3, retry_delay=1.0)

    with aioresponses() as mocked:
        # Mock 3 failed responses
        mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]
        mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]
        mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]

        async with Fetcher(config) as fetcher:
            start = time.time()
            with pytest.raises(ClientResponseError):
                await fetcher.fetch(url)
            elapsed = time.time() - start

    # Verify that retry delays were applied (3 attempts + 2 delays = ~2.0 seconds)
    assert elapsed == pytest.approx(2.0, abs=RETRY_TIMING_TOLERANCE)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_retry_then_success() -> None:
    """Test that retry succeeds after initial failures.

    Expects the fetcher to retry and eventually succeed.
    Also verifies timing for retry attempts.
    """
    url = "http://example.com/retry"
    config = FetcherConfig(retry_attempts=3, retry_delay=1.0)

    with aioresponses() as mocked:
        # Mock 2 failed responses, then a successful one
        mocked.get(url, status=500)  # pyright: ignore[reportUnknownMemberType]
        mocked.get(url, status=500)  # pyright: ignore[reportUnknownMemberType]
        mocked.get(url, status=200, body="success after retries")  # pyright: ignore[reportUnknownMemberType]

        async with Fetcher(config) as fetcher:
            start = time.time()
            content = await fetcher.fetch(url)
            elapsed = time.time() - start

            assert content == "success after retries"

    # Verify that retry delays were applied (2 retries = 2 * 1.0 = ~2.0 seconds)
    assert elapsed == pytest.approx(2.0, abs=RETRY_TIMING_TOLERANCE)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_retry_on_connection_error() -> None:
    """Test that connection errors trigger retry attempts.

    Expects the fetcher to retry on network failures.
    Also verifies retry timing for connection errors.
    """
    url = "http://example.com/connection-error"
    config = FetcherConfig(retry_attempts=2, retry_delay=1.0)

    with aioresponses() as mocked:
        # Mock connection errors
        mocked.get(url, exception=ClientError("Connection failed"))  # pyright: ignore[reportUnknownMemberType]
        mocked.get(url, exception=ClientError("Connection failed"))  # pyright: ignore[reportUnknownMemberType]
        mocked.get(url, status=200, body="success after connection retry")  # pyright: ignore[reportUnknownMemberType]

        async with Fetcher(config) as fetcher:
            start = time.time()
            content = await fetcher.fetch(url)
            elapsed = time.time() - start

            assert content == "success after connection retry"

    # Verify that retry delays were applied (2 retries = 2 * 1.0 = ~2.0 seconds)
    assert elapsed == pytest.approx(2.0, abs=RETRY_TIMING_TOLERANCE)  # pyright: ignore[reportUnknownMemberType]


@pytest.mark.asyncio
async def test_fetcher_retry_exhausted() -> None:
    """Test that retry attempts are exhausted and final error is raised.

    Expects the fetcher to fail after all retry attempts are used.
    Also verifies that all retry delays are properly applied.
    """
    url = "http://example.com/always-fail"
    config = FetcherConfig(retry_attempts=2, retry_delay=1.0)

    with aioresponses() as mocked:
        # Mock persistent failures
        mocked.get(url, status=500, repeat=True)  # pyright: ignore[reportUnknownMemberType]

        async with Fetcher(config) as fetcher:
            start = time.time()
            with pytest.raises(ClientResponseError):
                await fetcher.fetch(url)
            elapsed = time.time() - start

    # Verify that retry delays were applied (2 retries = 2 * 1.0 = ~2.0 seconds)
    assert elapsed == pytest.approx(2.0, abs=RETRY_TIMING_TOLERANCE)  # pyright: ignore[reportUnknownMemberType]
