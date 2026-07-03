"""Tests for netutil module."""

from unittest.mock import MagicMock, patch

from pyapollo.core.netutil import get_local_ip


def test_get_local_ip_explicit() -> None:
    assert get_local_ip("192.168.1.10") == "192.168.1.10"


@patch("pyapollo.core.netutil.socket.socket")
def test_get_local_ip_detect_success(mock_socket_cls: MagicMock) -> None:
    mock_sock = MagicMock()
    mock_sock.getsockname.return_value = ("10.0.0.5", 0)
    mock_socket_cls.return_value = mock_sock

    assert get_local_ip(None) == "10.0.0.5"
    mock_sock.connect.assert_called_once_with(("8.8.8.8", 53))
    mock_sock.close.assert_called_once()


@patch("pyapollo.core.netutil.socket.socket", side_effect=OSError("no network"))
def test_get_local_ip_detect_failure(mock_socket_cls: MagicMock) -> None:
    del mock_socket_cls
    assert get_local_ip(None) == "127.0.0.1"
