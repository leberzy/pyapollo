"""Synchronous HTTP transport and config service discovery for Apollo."""

from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import requests

from pyapollo.core.exceptions import ApolloClientError, ServerNotResponseException
from pyapollo.core.models import ConfigResult, Notification, ServiceInstance, parse_notification_id
from pyapollo.core.signature import build_auth_headers
from pyapollo.core.urls import (
    build_config_url,
    build_meta_service_url,
    build_notifications_url,
    normalize_homepage_url,
    parse_homepage_url,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HttpResult:
    status: int
    json_body: Any | None
    text: str | None


class SyncTransport(ABC):
    @abstractmethod
    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        params: dict[str, str] | None = None,
    ) -> HttpResult:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class RequestsTransport(SyncTransport):
    """HTTP transport backed by ``requests.Session`` (connection reuse)."""

    def __init__(self, default_timeout: float = 10) -> None:
        self._session = requests.Session()
        self._default_timeout = default_timeout

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        params: dict[str, str] | None = None,
    ) -> HttpResult:
        effective_timeout = timeout if timeout is not None else self._default_timeout
        try:
            response = self._session.get(
                url,
                headers=headers or {},
                timeout=effective_timeout,
                params=params,
            )
        except requests.exceptions.Timeout as exc:
            raise ServerNotResponseException(f"Request to {url} timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ServerNotResponseException(f"Failed to connect to {url}.") from exc

        json_body: Any | None
        try:
            json_body = response.json()
        except ValueError:
            json_body = None

        return HttpResult(
            status=response.status_code,
            json_body=json_body,
            text=response.text,
        )

    def close(self) -> None:
        self._session.close()


def parse_service_instances(payload: Any) -> list[ServiceInstance]:
    """Parse meta ``/services/config`` JSON into ``ServiceInstance`` list."""
    if not isinstance(payload, list):
        return []
    services: list[ServiceInstance] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        homepage = item.get("homepageUrl")
        if not homepage or not isinstance(homepage, str):
            continue
        instance_id = item.get("instanceId")
        services.append(
            ServiceInstance(
                home_page_url=homepage,
                instance_id=instance_id if isinstance(instance_id, str) else None,
            )
        )
    return services


class ConfigServiceLocator:
    """
    Discover Apollo config service instances.

    Mirrors Java ``ConfigServiceLocator``:
    - custom config server list bypasses meta discovery
    - meta: ``GET {meta}/services/config?appId=&ip=``
    - caches last successful service list
    """

    def __init__(
        self,
        transport: SyncTransport,
        *,
        meta_server_address: str | None = None,
        app_id: str | None = None,
        local_ip: str | None = None,
        custom_homepage_urls: list[str] | None = None,
        discovery_timeout: float = 10,
    ) -> None:
        self._transport = transport
        self._meta_server_address = meta_server_address
        self._app_id = app_id
        self._local_ip = local_ip
        self._custom_homepage_urls = custom_homepage_urls
        self._discovery_timeout = discovery_timeout
        self._cached_services: list[ServiceInstance] = []

    def set_custom_homepage_urls(self, urls: list[str] | None) -> None:
        self._custom_homepage_urls = urls
        if urls:
            self._cached_services = [ServiceInstance(home_page_url=u.rstrip("/")) for u in urls]

    def discover(self, exclude_homepage: str | None = None) -> list[ServiceInstance]:
        if self._custom_homepage_urls:
            services = [
                ServiceInstance(home_page_url=u.rstrip("/")) for u in self._custom_homepage_urls
            ]
        else:
            services = self._discover_from_meta()
            if services:
                self._cached_services = services
            elif self._cached_services:
                services = self._cached_services
            else:
                raise ApolloClientError("No apollo config service found")

        if exclude_homepage:
            excluded = normalize_homepage_url(exclude_homepage)
            services = [
                s for s in services if normalize_homepage_url(s.home_page_url) != excluded
            ]
        if not services:
            raise ApolloClientError("No available config server after exclusion")
        return services

    def choose_one(self, exclude_homepage: str | None = None) -> ServiceInstance:
        services = list(self.discover(exclude_homepage))
        random.shuffle(services)
        return services[0]

    def _discover_from_meta(self) -> list[ServiceInstance]:
        if not self._meta_server_address or not self._app_id:
            raise ApolloClientError("meta_server_address and app_id are required for discovery")

        url = build_meta_service_url(self._meta_server_address, self._app_id, self._local_ip)
        logger.debug("Discovering config services from meta: %s", url)
        result = self._transport.get(url, timeout=self._discovery_timeout)
        if result.status != 200 or result.json_body is None:
            msg = f"Failed to discover config services from {url}, status={result.status}"
            raise ApolloClientError(msg)
        services = parse_service_instances(result.json_body)
        if not services:
            raise ApolloClientError(f"No apollo service found at {url}")
        return services


class ApolloConfigApi:
    """
    High-level Apollo Config Service HTTP API (sync).

    Aligns with Java ``RemoteConfigRepository`` and ``RemoteConfigLongPollService``.
    """

    def __init__(
        self,
        transport: SyncTransport,
        *,
        app_id: str,
        app_secret: str | None,
        cluster: str,
        local_ip: str | None = None,
        label: str | None = None,
        data_center: str | None = None,
        default_timeout: float = 10,
    ) -> None:
        self._transport = transport
        self._app_id = app_id
        self._app_secret = app_secret
        self._cluster = cluster
        self._local_ip = local_ip
        self._label = label
        self._data_center = data_center
        self._default_timeout = default_timeout

    def fetch_config(
        self,
        homepage_url: str,
        namespace: str,
        *,
        release_key: str | None = None,
        messages: dict[str, object] | None = None,
        timeout: float | None = None,
    ) -> ConfigResult | None:
        """
        Fetch namespace config. Returns ``None`` when server responds 304 (not modified).
        """
        url = build_config_url(
            homepage_url.rstrip("/"),
            self._app_id,
            self._cluster,
            namespace,
            release_key=release_key,
            ip=self._local_ip,
            label=self._label,
            data_center=self._data_center,
            messages=messages,
        )
        headers = build_auth_headers(url, self._app_id, self._app_secret)
        result = self._transport.get(
            url,
            headers=headers,
            timeout=timeout if timeout is not None else self._default_timeout,
        )

        if result.status == 304:
            logger.debug("Config server responds with 304 for namespace %s", namespace)
            return None
        if result.status != 200 or not isinstance(result.json_body, dict):
            msg = f"Unexpected status {result.status} fetching config from {url}"
            raise ApolloClientError(msg)

        body = result.json_body
        configurations = body.get("configurations", {})
        if not isinstance(configurations, dict):
            configurations = {}
        str_config = {str(k): str(v) for k, v in configurations.items()}
        release_key_value = body.get("releaseKey")
        return ConfigResult(
            app_id=self._app_id,
            cluster=self._cluster,
            namespace=namespace,
            configurations=str_config,
            release_key=str(release_key_value) if release_key_value is not None else None,
        )

    def poll_notifications(
        self,
        homepage_url: str,
        notifications: list[Notification],
        *,
        timeout: float,
    ) -> list[Notification]:
        """
        Long-poll ``/notifications/v2``. Returns updated notifications (status 200),
        or empty list on 304.
        """
        url = build_notifications_url(
            homepage_url.rstrip("/"),
            self._app_id,
            self._cluster,
            notifications,
            ip=self._local_ip,
            label=self._label,
            data_center=self._data_center,
        )
        headers = build_auth_headers(url, self._app_id, self._app_secret)
        result = self._transport.get(url, headers=headers, timeout=timeout)

        if result.status == 304:
            return []
        if result.status != 200 or not isinstance(result.json_body, list):
            msg = f"Unexpected status {result.status} polling notifications from {url}"
            raise ApolloClientError(msg)

        updated: list[Notification] = []
        for item in result.json_body:
            if not isinstance(item, dict):
                continue
            ns = item.get("namespaceName")
            nid = item.get("notificationId")
            if not isinstance(ns, str):
                continue
            notification_id = parse_notification_id(nid)
            messages = item.get("messages")
            msg_dict = messages if isinstance(messages, dict) else None
            updated.append(
                Notification(
                    namespace_name=ns,
                    notification_id=notification_id,
                    messages=msg_dict,
                )
            )
        return updated


def service_to_endpoint(service: ServiceInstance) -> tuple[str, str, int]:
    """Return (homepage_url, scheme_host, port) from a service instance."""
    base, port = parse_homepage_url(service.home_page_url)
    return service.home_page_url, base, port
