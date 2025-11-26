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
...     print(response)
<html>...</html>
<html>...</html>
<html>...</html>
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
