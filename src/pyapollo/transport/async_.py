"""Asynchronous HTTP transport and config service discovery for Apollo."""

from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import aiohttp

from pyapollo.core.exceptions import ApolloClientError, ServerNotResponseException
from pyapollo.core.models import ConfigResult, Notification, ServiceInstance, parse_notification_id
from pyapollo.core.signature import build_auth_headers
from pyapollo.core.urls import (
    build_config_url,
    build_meta_service_url,
    build_notifications_url,
    normalize_homepage_url,
)

from .sync import parse_service_instances, service_to_endpoint

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HttpResult:
    status: int
    json_body: Any | None
    text: str | None


class AsyncTransport(ABC):
    @abstractmethod
    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        params: dict[str, str] | None = None,
    ) -> HttpResult:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class AiohttpTransport(AsyncTransport):
    """HTTP transport backed by ``aiohttp.ClientSession``."""

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        default_timeout: float = 10,
    ) -> None:
        self._session = session
        self._owns_session = session is None
        self._default_timeout = default_timeout

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def ensure_session(self) -> aiohttp.ClientSession:
        return await self._ensure_session()

    @property
    def session(self) -> aiohttp.ClientSession | None:
        return self._session

    @property
    def owns_session(self) -> bool:
        """Whether this transport created the session and should close it."""
        return self._owns_session

    async def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        params: dict[str, str] | None = None,
    ) -> HttpResult:
        session = await self._ensure_session()
        effective_timeout = timeout if timeout is not None else self._default_timeout
        client_timeout = aiohttp.ClientTimeout(total=effective_timeout)
        try:
            async with session.get(
                url,
                headers=headers or {},
                timeout=client_timeout,
                params=params,
            ) as response:
                text = await response.text()
                json_body: Any | None
                try:
                    json_body = await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError):
                    json_body = None
                return HttpResult(status=response.status, json_body=json_body, text=text)
        except TimeoutError as exc:
            raise ServerNotResponseException(f"Request to {url} timed out.") from exc
        except aiohttp.ClientConnectionError as exc:
            raise ServerNotResponseException(f"Failed to connect to {url}.") from exc

    async def close(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None


class AsyncConfigServiceLocator:
    """Async config service discovery (mirrors sync ``ConfigServiceLocator``)."""

    def __init__(
        self,
        transport: AsyncTransport,
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

    async def discover(self, exclude_homepage: str | None = None) -> list[ServiceInstance]:
        if self._custom_homepage_urls:
            services = [
                ServiceInstance(home_page_url=u.rstrip("/")) for u in self._custom_homepage_urls
            ]
        else:
            services = await self._discover_from_meta()
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

    async def choose_one(self, exclude_homepage: str | None = None) -> ServiceInstance:
        services = list(await self.discover(exclude_homepage))
        random.shuffle(services)
        return services[0]

    async def _discover_from_meta(self) -> list[ServiceInstance]:
        if not self._meta_server_address or not self._app_id:
            raise ApolloClientError("meta_server_address and app_id are required for discovery")

        url = build_meta_service_url(self._meta_server_address, self._app_id, self._local_ip)
        logger.debug("Discovering config services from meta: %s", url)
        result = await self._transport.get(url, timeout=self._discovery_timeout)
        if result.status != 200 or result.json_body is None:
            msg = f"Failed to discover config services from {url}, status={result.status}"
            raise ApolloClientError(msg)
        services = parse_service_instances(result.json_body)
        if not services:
            raise ApolloClientError(f"No apollo service found at {url}")
        return services


class AsyncApolloConfigApi:
    """High-level Apollo Config Service HTTP API (async)."""

    def __init__(
        self,
        transport: AsyncTransport,
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

    async def fetch_config(
        self,
        homepage_url: str,
        namespace: str,
        *,
        release_key: str | None = None,
        messages: dict[str, object] | None = None,
        timeout: float | None = None,
    ) -> ConfigResult | None:
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
        result = await self._transport.get(
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

    async def poll_notifications(
        self,
        homepage_url: str,
        notifications: list[Notification],
        *,
        timeout: float,
    ) -> list[Notification]:
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
        result = await self._transport.get(url, headers=headers, timeout=timeout)

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


__all__ = [
    "AiohttpTransport",
    "AsyncApolloConfigApi",
    "AsyncConfigServiceLocator",
    "AsyncTransport",
    "HttpResult",
    "service_to_endpoint",
]
