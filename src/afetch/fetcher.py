# -*- coding: utf-8 -*-

"""
Core afetch implementation.
"""

import typing as t

from .config import FetcherConfig


class Fetcher:
    def __init__(self, config: FetcherConfig | None = None):
        pass

    async def fetch(self, url: str):
        raise NotImplementedError("Fetch method not implemented.")

    async def fetch_all(self, urls: t.Iterable[str]):
        raise NotImplementedError("Fetch all method not implemented.")

    def __aenter__(self):
        raise NotImplementedError("Async context manager enter not implemented.")

    def __aexit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError("Async context manager exit not implemented.")
