"""Tests for signature module."""

import hashlib
import hmac
from unittest.mock import patch

from pyapollo.core.signature import build_auth_headers, sign, url_to_path_with_query


def test_sign_known_value() -> None:
    secret = "secret"
    message = "hello"
    expected = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    import base64

    assert sign(message, secret) == base64.b64encode(expected).decode("utf-8")


def test_url_to_path_with_query() -> None:
    assert url_to_path_with_query("http://host/configs/a/b/c?releaseKey=1") == (
        "/configs/a/b/c?releaseKey=1"
    )
    assert url_to_path_with_query("http://host/") == "/"


def test_build_auth_headers_without_secret() -> None:
    assert build_auth_headers("http://host/configs", "app", None) == {}


@patch("pyapollo.core.signature.time.time", return_value=1.0)
def test_build_auth_headers_with_secret(mock_time: object) -> None:
    del mock_time
    headers = build_auth_headers(
        "http://host/configs/app/default/application",
        "my-app",
        "secret",
    )
    assert headers["Authorization"].startswith("Apollo my-app:")
    assert headers["Timestamp"] == str(int(1.0 * 1000))
