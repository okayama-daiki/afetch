"""Tests for the new Fetcher API features."""

from __future__ import annotations

import logging
import typing as t

import pytest
from aiohttp_client_cache.backends.base import CacheBackend
from yarl import URL

from afetch import (
    Fetcher,
    FetcherConfig,
    RequestOptions,
    ResponseError,
    ResponseType,
)

if t.TYPE_CHECKING:
    from pytest_httpserver import HTTPServer


@pytest.fixture
async def fetcher_with_headers() -> t.AsyncGenerator[Fetcher, None]:
    """Test fixture providing a Fetcher with default headers."""
    config = FetcherConfig(
        cache_backend=CacheBackend(),
        default_headers={"User-Agent": "afetch-test", "Accept": "application/json"},
    )
    async with Fetcher(config) as fetcher:
        yield fetcher


@pytest.fixture
async def fetcher_with_return_exceptions() -> t.AsyncGenerator[Fetcher, None]:
    """Test fixture providing a Fetcher configured to return exceptions."""
    config = FetcherConfig(
        cache_backend=CacheBackend(),
        return_exceptions=True,
    )
    async with Fetcher(config) as fetcher:
        yield fetcher


@pytest.fixture
def json_url(httpserver: HTTPServer) -> URL:
    """Test fixture providing a URL that returns JSON."""
    url = URL(f"http://localhost:{httpserver.port}/json")
    httpserver.expect_request(url.path).respond_with_json({"message": "hello", "count": 42})
    return url


@pytest.fixture
def post_url(httpserver: HTTPServer) -> URL:
    """Test fixture providing a URL that accepts POST requests."""
    url = URL(f"http://localhost:{httpserver.port}/post")
    httpserver.expect_request(
        url.path,
        method="POST",
    ).respond_with_data("post received")
    return url


@pytest.fixture
def error_url(httpserver: HTTPServer) -> URL:
    """Test fixture providing a URL that returns an error."""
    url = URL(f"http://localhost:{httpserver.port}/error")
    httpserver.expect_request(url.path).respond_with_data("server error", status=500)
    return url


class TestRequestMethod:
    """Tests for the new request() method."""

    async def test_request_get_text(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test GET request with text response."""
        url = URL(f"http://localhost:{httpserver.port}/text")
        httpserver.expect_request(url.path).respond_with_data("hello world")

        result = await fetcher_with_headers.request(url)
        assert result == "hello world"

    async def test_request_get_json(
        self,
        fetcher_with_headers: Fetcher,
        json_url: URL,
    ) -> None:
        """Test GET request with JSON response."""
        options = RequestOptions(response_type=ResponseType.JSON)
        result = await fetcher_with_headers.request(json_url, options)

        expected_count = 42
        assert isinstance(result, dict)
        assert result["message"] == "hello"
        assert result["count"] == expected_count

    async def test_request_get_bytes(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test GET request with bytes response."""
        url = URL(f"http://localhost:{httpserver.port}/bytes")
        httpserver.expect_request(url.path).respond_with_data(b"binary data")

        options = RequestOptions(response_type=ResponseType.BYTES)
        result = await fetcher_with_headers.request(url, options)

        assert isinstance(result, bytes)
        assert result == b"binary data"

    async def test_request_post(
        self,
        fetcher_with_headers: Fetcher,
        post_url: URL,
    ) -> None:
        """Test POST request."""
        options = RequestOptions(method="POST")
        result = await fetcher_with_headers.request(post_url, options)
        assert result == "post received"

    async def test_request_post_with_json_body(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test POST request with JSON body."""
        url = URL(f"http://localhost:{httpserver.port}/post-json")
        httpserver.expect_request(
            url.path,
            method="POST",
        ).respond_with_json({"status": "ok"})

        options = RequestOptions(
            method="POST",
            json={"name": "test"},
            response_type=ResponseType.JSON,
        )
        result = await fetcher_with_headers.request(url, options)

        assert isinstance(result, dict)
        assert result["status"] == "ok"


class TestHeaderMerging:
    """Tests for header merging functionality."""

    async def test_default_headers_applied(
        self,
        httpserver: HTTPServer,
    ) -> None:
        """Test that default headers are applied to requests."""
        url = URL(f"http://localhost:{httpserver.port}/headers")
        httpserver.expect_request(url.path).respond_with_data("afetch-test")

        config = FetcherConfig(
            cache_backend=CacheBackend(),
            default_headers={"User-Agent": "afetch-test"},
        )
        async with Fetcher(config) as fetcher:
            result = await fetcher.request(url)
            assert result == "afetch-test"

    async def test_per_request_headers_override_defaults(
        self,
        httpserver: HTTPServer,
    ) -> None:
        """Test that per-request headers override defaults."""
        url = URL(f"http://localhost:{httpserver.port}/headers-override")
        httpserver.expect_request(url.path).respond_with_data("custom-agent")

        config = FetcherConfig(
            cache_backend=CacheBackend(),
            default_headers={"User-Agent": "default-agent"},
        )
        async with Fetcher(config) as fetcher:
            options = RequestOptions(headers={"User-Agent": "custom-agent"})
            result = await fetcher.request(url, options)
            assert result == "custom-agent"


class TestResponseTypes:
    """Tests for different response types."""

    async def test_response_type_raw(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test RAW response type returns the response object."""
        url = URL(f"http://localhost:{httpserver.port}/raw")
        httpserver.expect_request(url.path).respond_with_data("raw content")

        options = RequestOptions(response_type=ResponseType.RAW)
        result = await fetcher_with_headers.request(url, options)

        # RAW type returns the ClientResponse object
        assert hasattr(result, "status")
        assert hasattr(result, "url")

    async def test_json_parse_error_raises_response_error(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test that JSON parse errors raise ResponseError."""
        url = URL(f"http://localhost:{httpserver.port}/invalid-json")
        httpserver.expect_request(url.path).respond_with_data("not valid json")

        options = RequestOptions(response_type=ResponseType.JSON)
        with pytest.raises(ResponseError, match="Failed to parse JSON response"):
            await fetcher_with_headers.request(url, options)


class TestErrorHandling:
    """Tests for error handling."""

    async def test_http_error_raises_response_error(
        self,
        error_url: URL,
    ) -> None:
        """Test that HTTP errors raise ResponseError."""
        config = FetcherConfig(
            cache_backend=CacheBackend(),
            retry_attempts=1,  # Don't retry
        )
        expected_status = 500
        async with Fetcher(config) as fetcher:
            with pytest.raises(ResponseError) as exc_info:
                await fetcher.request(error_url)

            assert exc_info.value.status == expected_status

    async def test_return_exceptions_in_fetch_all(
        self,
        fetcher_with_return_exceptions: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test that fetch_all returns exceptions when configured."""
        good_url = URL(f"http://localhost:{httpserver.port}/good")
        bad_url = URL(f"http://localhost:{httpserver.port}/bad")

        httpserver.expect_request(good_url.path).respond_with_data("good")
        httpserver.expect_request(bad_url.path).respond_with_data("error", status=500)

        options = RequestOptions()
        results = await fetcher_with_return_exceptions.fetch_all([good_url, bad_url], options)

        expected_len = 2
        assert len(results) == expected_len
        assert results[0] == "good"
        assert isinstance(results[1], Exception)


class TestLogging:
    """Tests for structured logging."""

    async def test_logging_on_request(
        self,
        httpserver: HTTPServer,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that requests are logged."""
        url = URL(f"http://localhost:{httpserver.port}/logged")
        httpserver.expect_request(url.path).respond_with_data("logged response")

        config = FetcherConfig(cache_backend=CacheBackend())
        with caplog.at_level(logging.DEBUG, logger="afetch"):
            async with Fetcher(config) as fetcher:
                await fetcher.request(url)

        # Check that debug logs were emitted
        assert any("Starting request" in record.message for record in caplog.records)
        assert any("Request completed" in record.message for record in caplog.records)

    async def test_custom_logger(
        self,
        httpserver: HTTPServer,
    ) -> None:
        """Test that custom logger is used when provided."""
        url = URL(f"http://localhost:{httpserver.port}/custom-logger")
        httpserver.expect_request(url.path).respond_with_data("logged")

        custom_logger = logging.getLogger("custom.afetch")
        custom_logger.setLevel(logging.DEBUG)

        # Create a handler to capture logs
        log_messages: list[str] = []
        handler = logging.Handler()
        handler.emit = lambda record: log_messages.append(record.getMessage())  # type: ignore[method-assign]
        custom_logger.addHandler(handler)

        config = FetcherConfig(
            cache_backend=CacheBackend(),
            logger=custom_logger,
        )

        async with Fetcher(config) as fetcher:
            await fetcher.request(url)

        assert any("Starting request" in msg for msg in log_messages)


class TestFetchAllWithOptions:
    """Tests for fetch_all with RequestOptions."""

    async def test_fetch_all_with_options(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test fetch_all with RequestOptions."""
        url1 = URL(f"http://localhost:{httpserver.port}/all1")
        url2 = URL(f"http://localhost:{httpserver.port}/all2")

        httpserver.expect_request(url1.path).respond_with_json({"id": 1})
        httpserver.expect_request(url2.path).respond_with_json({"id": 2})

        options = RequestOptions(response_type=ResponseType.JSON)
        results = await fetcher_with_headers.fetch_all([url1, url2], options)

        expected_len = 2
        assert len(results) == expected_len
        assert results[0] == {"id": 1}
        assert results[1] == {"id": 2}


class TestHttpMethods:
    """Tests for different HTTP methods."""

    async def test_put_request(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test PUT request."""
        url = URL(f"http://localhost:{httpserver.port}/put")
        httpserver.expect_request(url.path, method="PUT").respond_with_data("put ok")

        options = RequestOptions(method="PUT")
        result = await fetcher_with_headers.request(url, options)
        assert result == "put ok"

    async def test_delete_request(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test DELETE request."""
        url = URL(f"http://localhost:{httpserver.port}/delete")
        httpserver.expect_request(url.path, method="DELETE").respond_with_data("deleted")

        options = RequestOptions(method="DELETE")
        result = await fetcher_with_headers.request(url, options)
        assert result == "deleted"

    async def test_patch_request(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test PATCH request."""
        url = URL(f"http://localhost:{httpserver.port}/patch")
        httpserver.expect_request(url.path, method="PATCH").respond_with_data("patched")

        options = RequestOptions(method="PATCH")
        result = await fetcher_with_headers.request(url, options)
        assert result == "patched"


class TestQueryParams:
    """Tests for query parameters."""

    async def test_request_with_params(
        self,
        fetcher_with_headers: Fetcher,
        httpserver: HTTPServer,
    ) -> None:
        """Test request with query parameters."""
        url = URL(f"http://localhost:{httpserver.port}/params")
        httpserver.expect_request(url.path, query_string={"key": "value", "page": "1"}).respond_with_data("params ok")

        options = RequestOptions(params={"key": "value", "page": "1"})
        result = await fetcher_with_headers.request(url, options)

        assert result == "params ok"
