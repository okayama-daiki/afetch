# afetch

A simple asynchronous HTTP client with just the essentials.

## Usage

```python
>>> from afetch import Fetcher
>>> urls = [
...     "https://example.com/xxx",
...     "https://example.com/yyy",
...     "https://example2.com",
... ]
>>> async with Fetcher() as fetcher:
...     responses = await fetcher.fetch_all(urls)
>>> for response in responses:
...     print(response.status_code, response.url)
200 https://example.com/xxx
200 https://example.com/yyy
200 https://example2.com
```

## For Developers

### Testing

```zsh
uv run pytest -v
```

### Formatting and Linting

```zsh
uv run ruff check .
```
