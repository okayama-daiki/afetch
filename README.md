# afetch

[![CI](https://github.com/okayama-daiki/afetch/actions/workflows/ci.yml/badge.svg)](https://github.com/okayama-daiki/afetch/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/okayama-daiki/afetch/graph/badge.svg)](https://codecov.io/gh/okayama-daiki/afetch)
[![PyPI Version](https://img.shields.io/pypi/v/afetch.svg)](https://pypi.python.org/pypi/afetch)
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/afetch.svg)](https://pypi.python.org/pypi/afetch)
[![License](https://img.shields.io/pypi/l/afetch.svg)](https://pypi.python.org/pypi/afetch)

A simple asynchronous HTTP client with just the essentials.

## Features

- **Rate Limiting** - Automatically limits requests per domain to avoid overwhelming servers
- **Automatic Retries** - Built-in exponential backoff retry mechanism for failed requests
- **Response Caching** - Cache responses to reduce redundant network calls
- **Concurrent Fetching** - Fetch multiple URLs in parallel with `fetch_all()`
- **Multiple HTTP Methods** - Support for GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
- **Response Handlers** - Configurable response handling (text, JSON, bytes, raw)
- **Custom Headers** - Default and per-request header support with merging
- **Configurable Timeouts** - Set timeouts at config and per-request levels
- **Structured Logging** - Built-in logging around request lifecycle
- **Error Hierarchy** - Dedicated exception types for different error cases

## Installation

```bash
pip install afetch
```

Or using [uv](https://docs.astral.sh/uv/):

```bash
uv add afetch
```

## Quick Start

```python
import asyncio
from afetch import Fetcher

async def main():
    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example2.com",
    ]
    # Simple one-liner for parallel fetching
    responses = await Fetcher.run(urls)
    for response in responses:
        print(response)

asyncio.run(main())
```

## Usage

### Simple Parallel Fetching

The simplest way to fetch multiple URLs in parallel:

```python
# One-liner without context manager
results = await Fetcher.run(["https://example.com/a", "https://example.com/b"])
```

### Fetching a Single URL

```python
async with Fetcher() as fetcher:
    content = await fetcher.fetch("https://example.com")
    print(content)
```

### Fetching Multiple URLs

```python
async with Fetcher() as fetcher:
    urls = ["https://example.com/a", "https://example.com/b"]
    responses = await fetcher.fetch_all(urls)
```

### Using the request() API

The `request()` method provides full control over HTTP requests:

```python
from afetch import Fetcher, RequestOptions, ResponseType

async with Fetcher() as fetcher:
    # GET request with JSON response
    options = RequestOptions(response_type=ResponseType.JSON)
    data = await fetcher.request("https://api.example.com/data", options)
    
    # POST request with JSON body
    options = RequestOptions(
        method="POST",
        json={"name": "test"},
        response_type=ResponseType.JSON,
    )
    result = await fetcher.request("https://api.example.com/create", options)
```

### Custom Headers

Set default headers for all requests and override per-request:

```python
from afetch import Fetcher, FetcherConfig, RequestOptions

config = FetcherConfig(
    default_headers={
        "User-Agent": "MyApp/1.0",
        "Accept": "application/json",
    }
)

async with Fetcher(config) as fetcher:
    # Uses default headers
    await fetcher.request("https://api.example.com/data")
    
    # Override specific headers per-request
    options = RequestOptions(headers={"User-Agent": "CustomAgent"})
    await fetcher.request("https://api.example.com/data", options)
```

### Response Types

Choose how to handle responses:

```python
from afetch import RequestOptions, ResponseType

# Get response as text (default)
options = RequestOptions(response_type=ResponseType.TEXT)

# Parse response as JSON
options = RequestOptions(response_type=ResponseType.JSON)

# Get response as bytes
options = RequestOptions(response_type=ResponseType.BYTES)

# Get raw aiohttp ClientResponse object
options = RequestOptions(response_type=ResponseType.RAW)
```

### Timeouts

Configure timeouts at the config level or per-request:

```python
from afetch import Fetcher, FetcherConfig, RequestOptions

# Default timeout for all requests
config = FetcherConfig(timeout=30.0)

async with Fetcher(config) as fetcher:
    # Override timeout for specific request
    options = RequestOptions(timeout=5.0)
    await fetcher.request("https://api.example.com/slow", options)
```

### Error Handling

Use the dedicated exception hierarchy:

```python
from afetch import (
    Fetcher,
    FetcherError,
    RequestError,
    ResponseError,
    FetcherTimeoutError,
)

async with Fetcher() as fetcher:
    try:
        await fetcher.request("https://api.example.com/data")
    except FetcherTimeoutError as e:
        print(f"Request timed out: {e.url}")
    except ResponseError as e:
        print(f"HTTP error {e.status}: {e.message}")
    except RequestError as e:
        print(f"Request failed: {e.cause}")
    except FetcherError as e:
        print(f"Fetcher error: {e}")
```

### Custom Configuration

```python
from afetch import Fetcher, FetcherConfig

config = FetcherConfig(
    max_rate_per_domain=2,      # Allow 2 requests per time period
    time_period_per_domain=1,   # Time period in seconds
    retry_attempts=5,           # Number of retry attempts
    cache_enabled=True,         # Enable response caching
    timeout=30.0,               # Default timeout in seconds
    return_exceptions=False,    # If True, fetch_all returns exceptions
)

async with Fetcher(config) as fetcher:
    content = await fetcher.fetch("https://example.com")
```

### Structured Logging

Afetch emits debug logs for request lifecycle:

```python
import logging
from afetch import Fetcher, FetcherConfig

# Enable debug logging for afetch
logging.getLogger("afetch").setLevel(logging.DEBUG)

# Or provide a custom logger
custom_logger = logging.getLogger("my_app.fetcher")
config = FetcherConfig(logger=custom_logger)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Clone the repository:

```bash
git clone https://github.com/okayama-daiki/afetch.git
cd afetch
```

2. Install dependencies with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

### Testing

```bash
uv run pytest -v
```

### Formatting and Linting

```bash
uv run ruff check .
```

## Acknowledgments

This project is built on top of these excellent libraries:

- [aiohttp](https://github.com/aio-libs/aiohttp) - Async HTTP client/server framework
- [aiohttp-client-cache](https://github.com/requests-cache/aiohttp-client-cache) - Async HTTP cache backend
- [aiohttp-retry](https://github.com/inyutin/aiohttp_retry) - Retry functionality for aiohttp
- [aiolimiter](https://github.com/mjpieters/aiolimiter) - Async rate limiter

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
