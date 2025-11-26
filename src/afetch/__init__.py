"""A simple asynchronous HTTP client with just the essentials."""

from .config import FetcherConfig
from .fetcher import Fetcher

__all__ = ["Fetcher", "FetcherConfig"]
__version__ = "0.1.0"
