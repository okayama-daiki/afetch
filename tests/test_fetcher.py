"""Tests for the afetch Fetcher class."""

import asyncio
import typing as t
from unittest.mock import patch
from urllib.parse import urlparse

from pytest_httpserver import RequestMatcher

from afetch import Fetcher, FetcherConfig

if t.TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


class _MockLoopTime:
    def __init__(self) -> None:
        self.current_time = 0
        event_loop = asyncio.get_running_loop()
        self.patch = patch.object(event_loop, "time", self.mocked_time)

    def mocked_time(self) -> int:
        return self.current_time

    def __enter__(self) -> t.Self:
        self.patch.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.patch.stop()


async def wait_until_blocked[T](
    *tasks: asyncio.Task[T],
    max_wait_iter: int = 100,
) -> set[asyncio.Task[T]]:
    """Wait until all tasks are blocked and return the list of pending tasks.

    Increasing `max_wait_iter` reduces flakiness in CI environments, but it may also slow down tests.
    TODO: Replace with more robust synchronization mechanism if needed.
    """
    iteration, pending = 0, set(tasks)
    while iteration < max_wait_iter and len(pending) > 0:
        iteration += 1
        _, pending = await asyncio.wait(
            pending,  # pyright: ignore[reportUnknownArgumentType]
            return_when=asyncio.FIRST_COMPLETED,
            timeout=0,
        )

    return pending


def _extract_path(url: str) -> str:
    """Extract path from URL for HTTPServer expectations."""
    parsed = urlparse(url)
    return parsed.path


async def test_fetcher_single_fetch(httpserver: HTTPServer) -> None:
    """Test that a single fetch returns the expected content.

    Expects the response content to match the mocked value.
    """
    url = f"http://localhost:{httpserver.port}/page"
    httpserver.expect_request(_extract_path(url)).respond_with_data("test content")

    async with Fetcher() as fetcher:
        content = await fetcher.fetch(url)
    assert content == "test content"


async def test_fetcher_same_domain_rate_limiting(httpserver: HTTPServer) -> None:
    """Test that requests to the same domain are rate-limited.

    Verifies that rate limiting is applied per domain.
    """
    urls = [
        f"http://localhost:{httpserver.port}/page1",
        f"http://localhost:{httpserver.port}/page2",
        f"http://localhost:{httpserver.port}/page3",
    ]
    for url in urls:
        httpserver.expect_request(_extract_path(url)).respond_with_data("test response")

    with _MockLoopTime() as mocked_time:
        async with Fetcher() as fetcher:
            tasks = [asyncio.Task(fetcher.fetch(url)) for url in urls]
            expected_done_tasks = 0

            pending = await wait_until_blocked(*tasks)
            expected_done_tasks += 1
            assert (
                len(tasks) - len(pending) == expected_done_tasks
            )  # First request is done immediately

            pending = await wait_until_blocked(*pending)
            assert (
                len(tasks) - len(pending) == expected_done_tasks
            )  # Second request waits due to rate limiting

            mocked_time.current_time += 1
            expected_done_tasks += 1
            pending = await wait_until_blocked(*pending)
            assert (
                len(tasks) - len(pending) == expected_done_tasks
            )  # Second request is done

            pending = await wait_until_blocked(*pending)
            assert (
                len(tasks) - len(pending) == expected_done_tasks
            )  # Third request waits due to rate limiting

            mocked_time.current_time += 1
            expected_done_tasks += 1
            pending = await wait_until_blocked(*pending)
            assert (
                len(tasks) - len(pending) == expected_done_tasks
            )  # Third request is done


async def test_fetcher_different_domains_parallel(
    httpserver: HTTPServer,
    httpserver2: HTTPServer,
    httpserver3: HTTPServer,
) -> None:
    """Test that requests to different domains are executed in parallel."""
    urls = [
        f"http://localhost:{httpserver.port}/page",
        f"http://localhost:{httpserver2.port}/page",
        f"http://localhost:{httpserver3.port}/page",
    ]
    for server, url in zip(
        [httpserver, httpserver2, httpserver3],
        urls,
        strict=True,
    ):
        server.expect_request(_extract_path(url)).respond_with_data("test response")

    async with Fetcher() as fetcher:
        tasks = [asyncio.Task(fetcher.fetch(url)) for url in urls]

        pending = await wait_until_blocked(*tasks)
        assert len(pending) == 0  # All requests are done immediately


async def test_fetcher_cached_requests(httpserver: HTTPServer) -> None:
    """Test that repeated requests to the same URL are served from cache after the first request.

    TODO: Mock cache behavior instead of relying on actual caching implementation.
    """
    urls = [f"http://localhost:{httpserver.port}/page"] * 3
    for url in urls:
        httpserver.expect_request(_extract_path(url)).respond_with_data(
            "cached response",
        )

    async with Fetcher() as fetcher:
        await fetcher.fetch_all(urls)

    assert (
        httpserver.get_matching_requests_count(
            RequestMatcher(_extract_path(urls[0])),
        )
        == 1
    )  # Only the first request hits the server


async def test_fetcher_retry_then_success(httpserver: HTTPServer) -> None:
    """Test that retry succeeds after initial failures.

    Expects the fetcher to retry and eventually succeed.
    Also verifies timing for retry attempts.
    """
    url = f"http://localhost:{httpserver.port}/retry"
    path = _extract_path(url)
    config = FetcherConfig(retry_attempts=3, retry_delay=1.0)

    httpserver.expect_request(path).respond_with_data("", status=500)
    httpserver.expect_request(path).respond_with_data("", status=500)
    httpserver.expect_request(path).respond_with_data("success after retry")

    with _MockLoopTime() as mocked_time:
        async with Fetcher(config) as fetcher:
            task = asyncio.create_task(fetcher.fetch(url))
            pending = await wait_until_blocked(task)
            assert len(pending) == 1  # First attempt is blocked due to failure

            mocked_time.current_time += 1  # After first failure
            pending = await wait_until_blocked(task)
            assert len(pending) == 1  # Second attempt is blocked due to failure

            mocked_time.current_time += 1  # After second failure
            pending = await wait_until_blocked(task)
            assert len(pending) == 0  # Third attempt succeeds


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
