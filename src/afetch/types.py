"""Request and response handling types for afetch.

This module provides dataclasses and protocols for request options
and response handling.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aiohttp import hdrs

if TYPE_CHECKING:
    from yarl import URL

# HTTP method type - reuses aiohttp's method string constants
# Users can use aiohttp.hdrs.METH_GET, aiohttp.hdrs.METH_POST, etc. or plain strings
HttpMethod = str


class ResponseType(enum.Enum):
    """Response handling types.

    Attributes:
        TEXT: Return response as text string (default).
        JSON: Parse response as JSON and return dict/list.
        BYTES: Return response as raw bytes.
        RAW: Return the aiohttp ClientResponse object.

    """

    TEXT = "text"
    JSON = "json"
    BYTES = "bytes"
    RAW = "raw"


@dataclass
class RequestOptions:
    """Per-request configuration options.

    Allows overriding default fetcher configuration on a per-request basis.
    Options not specified (None) will use the fetcher's default values.

    Attributes:
        method: HTTP method to use (defaults to GET).
        headers: Additional headers to merge with default headers.
        data: Request body data for POST/PUT/PATCH requests.
        json: JSON body data (will be serialized).
        params: Query parameters to append to URL.
        timeout: Request timeout in seconds.
        response_type: How to handle the response.
        allow_redirects: Whether to follow redirects.

    """

    method: HttpMethod = hdrs.METH_GET
    headers: dict[str, str] = field(default_factory=dict)
    data: bytes | str | None = None
    json: Any | None = None
    params: dict[str, str] | None = None
    timeout: float | None = None
    response_type: ResponseType = ResponseType.TEXT
    allow_redirects: bool = True


@dataclass
class Request:
    """A request with URL and optional per-request options.

    This allows bundling a URL with its specific options for use with
    Fetcher.run_requests() when different requests need different options.

    Attributes:
        url: The URL to fetch.
        options: Optional request options specific to this URL.

    Example:
        ```python
        requests = [
            Request("https://api.example.com/users", RequestOptions(response_type=ResponseType.JSON)),
            Request("https://api.example.com/data", RequestOptions(method="POST", json={"key": "value"})),
        ]
        results = await Fetcher.run_requests(requests)
        ```

    """

    url: str | URL
    options: RequestOptions | None = None
