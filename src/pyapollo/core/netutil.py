"""Network utility helpers."""

from __future__ import annotations

import socket
from urllib.parse import urlparse


def get_local_ip(explicit: str | None, *, hint_host: str | None = None) -> str:
    """Return explicit IP or detect local outbound IP, falling back to 127.0.0.1."""
    if explicit is not None:
        return explicit

    targets: list[tuple[str, int]] = []
    if hint_host:
        normalized = hint_host if "://" in hint_host else f"http://{hint_host}"
        parsed = urlparse(normalized)
        if parsed.hostname:
            targets.append((parsed.hostname, parsed.port or 80))

    targets.append(("8.8.8.8", 53))

    for host, port in targets:
        sock: socket.socket | None = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((host, port))
            return str(sock.getsockname()[0])
        except OSError:
            continue
        finally:
            if sock is not None:
                sock.close()

    return "127.0.0.1"
