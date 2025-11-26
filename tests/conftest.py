"""Common test fixtures for the afetch project."""

import typing as t

import pytest
from pytest_httpserver import HTTPServer


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
