"""Apollo request signing and auth header building."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import urlparse

from .constants import (
    AUTHORIZATION_FORMAT,
    HTTP_HEADER_AUTHORIZATION,
    HTTP_HEADER_TIMESTAMP,
)


def sign(string_to_sign: str, secret: str) -> str:
    """Sign a string with HMAC-SHA1 and return base64-encoded digest."""
    signature = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


def url_to_path_with_query(url: str) -> str:
    """Extract path and query from a URL for signing."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return path + query


def build_auth_headers(
    url: str,
    app_id: str,
    secret: str | None,
) -> dict[str, str]:
    """Build Apollo authorization headers. Returns empty dict when secret is absent."""
    if not secret:
        return {}

    timestamp = str(int(time.time() * 1000))
    path_with_query = url_to_path_with_query(url)
    string_to_sign = f"{timestamp}\n{path_with_query}"
    signature = sign(string_to_sign, secret)

    return {
        HTTP_HEADER_AUTHORIZATION: AUTHORIZATION_FORMAT.format(app_id, signature),
        HTTP_HEADER_TIMESTAMP: timestamp,
    }
