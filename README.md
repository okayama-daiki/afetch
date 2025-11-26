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
    async with Fetcher() as fetcher:
        responses = await fetcher.fetch_all(urls)
    for response in responses:
        print(response)

asyncio.run(main())
```

## Usage

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

### Custom Configuration

```python
from afetch import Fetcher, FetcherConfig

config = FetcherConfig(
    max_rate_per_domain=2,      # Allow 2 requests per time period
    time_period_per_domain=1,   # Time period in seconds
    retry_attempts=5,           # Number of retry attempts
    cache_enabled=True,         # Enable response caching
)

async with Fetcher(config) as fetcher:
    content = await fetcher.fetch("https://example.com")
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
