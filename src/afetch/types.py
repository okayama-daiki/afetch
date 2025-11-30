"""Request and response handling types for afetch.

This module provides dataclasses and protocols for request options
and response handling.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Literal

# HTTP method type - uses string literals compatible with aiohttp
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]


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

    method: HttpMethod = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    data: bytes | str | None = None
    json: Any | None = None
    params: dict[str, str] | None = None
    timeout: float | None = None
    response_type: ResponseType = ResponseType.TEXT
    allow_redirects: bool = True
