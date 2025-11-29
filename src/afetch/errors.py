"""Error hierarchy for afetch.

This module provides a dedicated exception hierarchy wrapping aiohttp and
aiohttp_retry exceptions with original context preserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp import ClientResponse


class FetcherError(Exception):
    """Base exception for all afetch errors.

    This exception wraps underlying aiohttp exceptions while preserving
    the original context for debugging purposes.

    Attributes:
        message: Human-readable error description.
        cause: The original exception that caused this error.
        url: The URL that was being fetched when the error occurred.

    """

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        url: str | None = None,
    ) -> None:
        """Initialize FetcherError.

        Args:
            message: Human-readable error description.
            cause: The original exception that caused this error.
            url: The URL that was being fetched when the error occurred.

        """
        super().__init__(message)
        self.message = message
        self.cause = cause
        self.url = url

    def __str__(self) -> str:
        """Return a string representation of the error."""
        parts = [self.message]
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.cause:
            parts.append(f"Caused by: {type(self.cause).__name__}: {self.cause}")
        return " | ".join(parts)


class RequestError(FetcherError):
    """Error that occurred during request execution.

    This includes network errors, DNS failures, and connection issues.
    """


class FetcherTimeoutError(FetcherError):
    """Request timed out."""


class ResponseError(FetcherError):
    """Error related to HTTP response processing.

    Attributes:
        status: HTTP status code if available.
        response: The aiohttp response object if available.

    """

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        url: str | None = None,
        status: int | None = None,
        response: ClientResponse | None = None,
    ) -> None:
        """Initialize ResponseError.

        Args:
            message: Human-readable error description.
            cause: The original exception that caused this error.
            url: The URL that was being fetched when the error occurred.
            status: HTTP status code.
            response: The aiohttp response object.

        """
        super().__init__(message, cause=cause, url=url)
        self.status = status
        self.response = response

    def __str__(self) -> str:
        """Return a string representation of the error."""
        parts = [self.message]
        if self.status:
            parts.append(f"Status: {self.status}")
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.cause:
            parts.append(f"Caused by: {type(self.cause).__name__}: {self.cause}")
        return " | ".join(parts)


class RetryExhaustedError(FetcherError):
    """All retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        url: str | None = None,
        attempts: int | None = None,
    ) -> None:
        """Initialize RetryExhaustedError.

        Args:
            message: Human-readable error description.
            cause: The original exception that caused this error.
            url: The URL that was being fetched when the error occurred.
            attempts: Number of retry attempts made.

        """
        super().__init__(message, cause=cause, url=url)
        self.attempts = attempts


class CacheError(FetcherError):
    """Error related to cache operations."""
