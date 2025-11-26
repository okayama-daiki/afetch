"""Common test fixtures for the afetch project."""

import typing as t

import pytest
from aiohttp_client_cache.backends.base import CacheBackend
from pytest_httpserver import HTTPServer
from yarl import URL

from afetch import Fetcher, FetcherConfig


@pytest.fixture
def httpserver2() -> t.Generator[HTTPServer]:
    """Test fixture providing a second local HTTP server for parallel testing."""
    server = HTTPServer(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def httpserver3() -> t.Generator[HTTPServer]:
    """Test fixture providing a third local HTTP server for parallel testing."""
    server = HTTPServer(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


@pytest.fixture
async def fetcher() -> t.AsyncGenerator[Fetcher]:
    """Test fixture providing a default instance of Fetcher."""
    config = FetcherConfig(cache_backend=CacheBackend())
    async with Fetcher(config) as fetcher:
        yield fetcher


@pytest.fixture
async def fetcher_retry_twice() -> t.AsyncGenerator[Fetcher]:
    """Test fixture providing an instance of Fetcher with 2 retry attempts."""
    config = FetcherConfig(
        cache_backend=CacheBackend(),
        retry_attempts=2,
    )
    async with Fetcher(config) as fetcher:
        yield fetcher


@pytest.fixture
def url(httpserver: HTTPServer) -> URL:
    """Test fixture providing a single URL."""
    url = URL(f"http://localhost:{httpserver.port}/page")
    httpserver.expect_request(url.path).respond_with_data("test response")
    return url


@pytest.fixture
def urls_same_domain(httpserver: HTTPServer) -> list[URL]:
    """Test fixture providing multiple URLs on the same domain."""
    urls = [
        URL(f"http://localhost:{httpserver.port}/page1"),
        URL(f"http://localhost:{httpserver.port}/page2"),
        URL(f"http://localhost:{httpserver.port}/page3"),
    ]

    for i, url in enumerate(urls, 1):
        httpserver.expect_request(url.path).respond_with_data(f"content{i}")

    return urls


@pytest.fixture
def urls_different_domains(
    httpserver: HTTPServer,
    httpserver2: HTTPServer,
    httpserver3: HTTPServer,
) -> list[URL]:
    """Test fixture providing multiple URLs on different domains."""
    urls = [
        URL(f"http://localhost:{httpserver.port}/page"),
        URL(f"http://localhost:{httpserver2.port}/page"),
        URL(f"http://localhost:{httpserver3.port}/page"),
    ]
    for server, url in zip([httpserver, httpserver2, httpserver3], urls, strict=True):
        server.expect_request(url.path).respond_with_data("test response")

    return urls


@pytest.fixture
def url_with_spy(httpserver: HTTPServer) -> tuple[URL, HTTPServer]:
    """Test fixture providing a single URL along with its HTTP server for spying."""
    url = URL(f"http://localhost:{httpserver.port}/cached")
    for _ in range(3):
        httpserver.expect_request(url.path).respond_with_data(
            "cached response",
        )
    return url, httpserver


@pytest.fixture
def url_error_after_success(httpserver: HTTPServer) -> URL:
    """Test fixture providing a URL that fails twice before succeeding."""
    url = URL(f"http://localhost:{httpserver.port}/error")
    httpserver.expect_request(url.path).respond_with_data(
        "error response",
        status=500,
    )
    httpserver.expect_request(url.path).respond_with_data(
        "error response",
        status=500,
    )
    httpserver.expect_request(url.path).respond_with_data(
        "successful response",
        status=200,
    )
    return url


@pytest.fixture
def url_always_fail(httpserver: HTTPServer) -> URL:
    """Test fixture providing a URL that always fails."""
    url = URL(f"http://localhost:{httpserver.port}/always-fail")
    for _ in range(5):
        httpserver.expect_request(url.path).respond_with_data(
            "always fail response",
            status=500,
        )
    return url
