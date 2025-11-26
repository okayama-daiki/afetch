"""Tests for the afetch Fetcher class."""

import asyncio
import typing as t
from unittest.mock import patch

import pytest
from aiohttp.client import ClientError
from aiohttp.client_exceptions import InvalidUrlClientError
from pytest_httpserver import RequestMatcher

from afetch import Fetcher

if t.TYPE_CHECKING:
    from pytest_httpserver import HTTPServer
    from yarl import URL


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


async def _wait_for_tasks_completion[T](
    *tasks: asyncio.Task[T],
    max_wait_iter: int = 1_000,
) -> set[asyncio.Task[T]]:
    """Wait a bit for tasks to complete and return the pending ones.

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


async def test_fetcher_single_fetch(
    fetcher: Fetcher,
    url: URL,
) -> None:
    """Test that a single fetch returns the expected content.

    Expects the response content to match the mocked value.
    """
    content = await fetcher.fetch(url)
    assert content == "test response"


async def test_fetcher_same_domain_rate_limiting(
    fetcher: Fetcher,
    urls_same_domain: list[URL],
) -> None:
    """Test that requests to the same domain are rate-limited.

    Verifies that rate limiting is applied per domain.
    """
    with _MockLoopTime() as mocked_time:
        tasks = [asyncio.Task(fetcher.fetch(url)) for url in urls_same_domain]
        expected_done_tasks = 0

        pending = await _wait_for_tasks_completion(*tasks)
        expected_done_tasks += 1
        assert (
            len(tasks) - len(pending) == expected_done_tasks
        )  # First request is done immediately

        pending = await _wait_for_tasks_completion(*pending)
        assert (
            len(tasks) - len(pending) == expected_done_tasks
        )  # Second request waits due to rate limiting

        mocked_time.current_time += 1
        expected_done_tasks += 1
        pending = await _wait_for_tasks_completion(*pending)
        assert (
            len(tasks) - len(pending) == expected_done_tasks
        )  # Second request is done

        pending = await _wait_for_tasks_completion(*pending)
        assert (
            len(tasks) - len(pending) == expected_done_tasks
        )  # Third request waits due to rate limiting

        mocked_time.current_time += 1
        expected_done_tasks += 1
        pending = await _wait_for_tasks_completion(*pending)
        assert len(tasks) - len(pending) == expected_done_tasks  # Third request is done


async def test_fetcher_different_domains_parallel(
    fetcher: Fetcher,
    urls_different_domains: list[URL],
) -> None:
    """Test that requests to different domains are executed in parallel."""
    tasks = [asyncio.Task(fetcher.fetch(url)) for url in urls_different_domains]

    pending = await _wait_for_tasks_completion(*tasks)
    assert len(pending) == 0  # All requests are done immediately


async def test_fetcher_cached_requests(
    fetcher: Fetcher,
    url_with_spy: tuple[URL, HTTPServer],
) -> None:
    """Test that repeated requests to the same URL are served from cache after the first request.

    TODO: Mock cache behavior instead of relying on actual caching implementation.
    """
    url, httpserver = url_with_spy

    await fetcher.fetch(url)
    await fetcher.fetch(url)
    await fetcher.fetch(url)

    assert (
        httpserver.get_matching_requests_count(RequestMatcher(url.path)) == 1
    )  # Only the first request hits the server


async def test_fetcher_retry_then_success(
    fetcher_retry_twice: Fetcher,
    url_error_after_success: URL,
) -> None:
    """Test that the fetcher retries failed requests and eventually succeeds.

    Expects the first two attempts to fail and the third to succeed.
    """
    with _MockLoopTime() as mocked_time:
        task = asyncio.create_task(fetcher_retry_twice.fetch(url_error_after_success))
        pending = await _wait_for_tasks_completion(task)
        assert len(pending) == 1  # First attempt is blocked due to failure

        pending = await _wait_for_tasks_completion(task)
        assert len(pending) == 1  # Second attempt is blocked due to failure

        pending = await _wait_for_tasks_completion(task)
        assert len(pending) == 1  # Delay before third attempt

        mocked_time.current_time += 1
        pending = await _wait_for_tasks_completion(task)
        assert len(pending) == 0  # Third attempt should succeed


async def test_fetcher_max_retries_exceeded(
    fetcher_retry_twice: Fetcher,
    url_always_fail: URL,
) -> None:
    """Test behavior when maximum retry attempts are exceeded."""
    with pytest.raises(ClientError):
        await fetcher_retry_twice.fetch(url_always_fail)


async def test_fetcher_invalid_url(fetcher: Fetcher) -> None:
    """Test handling of invalid URLs."""
    with pytest.raises(InvalidUrlClientError, match="not-a-url"):
        await fetcher.fetch("not-a-url")


async def test_fetcher_context_manager_required() -> None:
    """Test that fetcher must be used as context manager."""
    fetcher = Fetcher()
    with pytest.raises(RuntimeError, match="must be used as async context manager"):
        await fetcher.fetch("http://example.com")


async def test_fetcher_fetch_all_same_domain(
    fetcher: Fetcher,
    urls_same_domain: list[URL],
) -> None:
    """Test fetch_all method with rate limiting on the same domain."""
    with _MockLoopTime() as mocked_time:
        task = asyncio.create_task(fetcher.fetch_all(urls_same_domain))

        await _wait_for_tasks_completion(task)
        assert not task.done()  # First request is done immediately

        mocked_time.current_time += 1
        await _wait_for_tasks_completion(task)
        assert not task.done()  # Second request may be done, Third is may be pending

        mocked_time.current_time += 1
        await _wait_for_tasks_completion(task)
        assert task.done()  # All requests should be done


async def test_fetcher_fetch_all_cached_requests(
    fetcher: Fetcher,
    url_with_spy: tuple[URL, HTTPServer],
) -> None:
    """Test fetch_all method with cached requests."""
    url, httpserver = url_with_spy
    urls = [url, url, url]

    await fetcher.fetch_all(urls)

    assert (
        httpserver.get_matching_requests_count(RequestMatcher(url.path)) == 1
    )  # Only the first request hits the server
