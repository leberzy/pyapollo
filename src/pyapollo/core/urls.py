"""URL building and parsing for Apollo HTTP API."""

from __future__ import annotations

import json
from urllib.parse import quote, urlencode, urlparse

from .constants import (
    CONFIGS_PATH_TEMPLATE,
    DEFAULT_CONFIG_SERVER_PORT,
    DEFAULT_FALLBACK_PORT,
    META_SERVICES_CONFIG_PATH,
    NOTIFICATIONS_PATH,
)
from .models import Notification


def normalize_homepage_url(homepage_url: str) -> str:
    """Normalize homepage URL for stable comparison (strip trailing slash)."""
    return homepage_url.rstrip("/")


def parse_homepage_url(homepage_url: str) -> tuple[str, int]:
    """
    Parse Apollo config service homepageUrl into (scheme://host, port).

    Replaces fragile manual ``split(':')`` parsing.
    """
    parsed = urlparse(homepage_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname
    if not host:
        msg = f"Invalid homepage URL: {homepage_url!r}"
        raise ValueError(msg)

    port = parsed.port
    if port is None:
        if scheme == "https":
            port = 443
        elif scheme == "http":
            port = 80
        else:
            port = DEFAULT_FALLBACK_PORT

    base = f"{scheme}://{host}"
    return base, port


def build_meta_service_url(
    meta_server_address: str,
    app_id: str,
    ip: str | None = None,
) -> str:
    """
    Build meta server discovery URL.

    Aligns with Java ``ConfigServiceLocator.assembleMetaServiceUrl``:
    ``{meta}/services/config?appId=...&ip=...``
    """
    query: dict[str, str] = {"appId": app_id}
    if ip:
        query["ip"] = ip
    base = meta_server_address.rstrip("/")
    return f"{base}/{META_SERVICES_CONFIG_PATH}?{urlencode(query)}"


def build_config_url(
    base: str,
    app_id: str,
    cluster: str,
    namespace: str,
    *,
    release_key: str | None = None,
    ip: str | None = None,
    label: str | None = None,
    data_center: str | None = None,
    messages: dict[str, object] | None = None,
) -> str:
    """Build the /configs/{appId}/{cluster}/{namespace} URL with optional query params."""
    path = CONFIGS_PATH_TEMPLATE.format(
        app_id=quote(app_id, safe=""),
        cluster=quote(cluster, safe=""),
        namespace=quote(namespace, safe=""),
    )
    query: dict[str, str] = {}
    if release_key:
        query["releaseKey"] = release_key
    if ip:
        query["ip"] = ip
    if label:
        query["label"] = label
    if data_center:
        query["dataCenter"] = data_center
    if messages is not None:
        query["messages"] = json.dumps(messages, separators=(",", ":"))

    base = base.rstrip("/")
    url = f"{base}/{path}"
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def build_notifications_url(
    base: str,
    app_id: str,
    cluster: str,
    notifications: list[Notification],
    *,
    ip: str | None = None,
    label: str | None = None,
    data_center: str | None = None,
) -> str:
    """Build the /notifications/v2 URL for long polling (Java RemoteConfigLongPollService)."""
    payload = [
        {
            "namespaceName": n.namespace_name,
            "notificationId": n.notification_id,
        }
        for n in notifications
    ]
    query: dict[str, str] = {
        "appId": app_id,
        "cluster": cluster,
        "notifications": json.dumps(payload, separators=(",", ":")),
    }
    if data_center:
        query["dataCenter"] = data_center
    if ip:
        query["ip"] = ip
    if label:
        query["label"] = label
    encoded = urlencode(query)
    base = base.rstrip("/")
    return f"{base}/{NOTIFICATIONS_PATH}?{encoded}"


def build_custom_config_server_url(host: str, port: int | None) -> tuple[str, str, int]:
    """Build config server URL parts from custom host/port settings."""
    normalized_host = host.rstrip("/")
    if "://" not in normalized_host:
        normalized_host = f"http://{normalized_host}"

    parsed = urlparse(normalized_host)
    resolved_port = port or parsed.port or DEFAULT_CONFIG_SERVER_PORT
    scheme = parsed.scheme or "http"
    hostname = parsed.hostname
    if not hostname:
        msg = f"Invalid config server host: {host!r}"
        raise ValueError(msg)

    scheme_host = f"{scheme}://{hostname}"
    config_server_url = f"{scheme_host}:{resolved_port}"
    return config_server_url, scheme_host, resolved_port
