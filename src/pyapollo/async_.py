"""
Asynchronous Apollo Python client implementation.

This is an asynchronous version of the Apollo Python client SDK.
It supports Python 3.7 to 3.13 and uses aiohttp for HTTP requests.

Key features:
- Fully asynchronous API
- Compatible with Python 3.7 to 3.13
- Thread-safe with asyncio locks
- Supports async context manager
- Implements Apollo's official HTTP API
- Supports configuration via environment variables and .env files

Implements Apollo's official HTTP API:
English: https://www.apolloconfig.com/#/en/client/other-language-client-user-guide
中文: https://www.apolloconfig.com/#/zh/client/other-language-client-user-guide
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import aiohttp

from pyapollo.cache import AsyncFileCache, MemoryCache, resolve_cache_root
from pyapollo.config import ApolloSettingsConfig
from pyapollo.config.settings import resolve_label
from pyapollo.core.constants import DEFAULT_NAMESPACE
from pyapollo.core.getters import (
    get_bool as cache_get_bool,
)
from pyapollo.core.getters import (
    get_float as cache_get_float,
)
from pyapollo.core.getters import (
    get_int as cache_get_int,
)
from pyapollo.core.getters import (
    get_json_value as cache_get_json_value,
)
from pyapollo.core.getters import (
    get_list as cache_get_list,
)
from pyapollo.core.getters import (
    get_value as cache_get_value,
)
from pyapollo.core.models import ConfigChangeEvent, ConfigResult, ServiceInstance
from pyapollo.core.netutil import get_local_ip
from pyapollo.core.urls import build_custom_config_server_url
from pyapollo.listeners import AsyncListenerRegistry, Subscription
from pyapollo.repository import AsyncConfigRepository, AsyncRepositoryHooks
from pyapollo.transport import (
    AiohttpTransport,
    AsyncApolloConfigApi,
    AsyncConfigServiceLocator,
    service_to_endpoint,
)

logger = logging.getLogger(__name__)


class AsyncApolloClient:
    """Asynchronous Apollo client based on the official HTTP API."""

    def __init__(
        self,
        meta_server_address: str | None = None,
        app_id: str | None = None,
        app_secret: str | None = None,
        cluster: str = "default",
        env: str = "DEV",
        namespaces: list[str] | None = None,
        ip: str | None = None,
        label: str | None = None,
        timeout: int = 10,
        cycle_time: int = 30,
        cache_file_dir_path: str | None = None,
        config_server_host: str | None = None,
        config_server_port: int | None = None,
        session: aiohttp.ClientSession | None = None,
        settings: ApolloSettingsConfig | None = None,
        *,
        autostart: bool = True,
    ):
        """
        Initialize method

        Args:
            meta_server_address: Apollo meta server address, format is like 'https://xxx/yyy'
            app_id: Application ID
            app_secret: Application secret, optional
            cluster: Cluster name, default value is 'default'
            env: Environment, default value is 'DEV'
            namespaces: Namespace list to get configuration, default value is ['application']
            timeout: HTTP request timeout seconds, default value is 10 seconds
            ip: Deploy IP for grey release, default value is the local IP
            label: Client label for gray release matching (Java apollo.label)
            cycle_time: Cycle time to update configuration content from server
            cache_file_dir_path: Directory path to store the configuration cache file
            config_server_host: Custom config server host (e.g., 'http://localhost'), if provided, will skip meta server discovery
            config_server_port: Custom config server port (e.g., 8080), used with config_server_host
            session: aiohttp client session, if not provided, a new one will be created
            settings: ApolloSettingsConfig instance, if provided other parameters will be ignored
            autostart: When ``True`` (default), ``async with`` will call ``start()`` on enter.

        You can initialize the client in three ways:
        1. Using environment variables (requires no parameters):
            ```python
            client = AsyncApolloClient()  # Will use environment variables with APOLLO_ prefix
            ```

        2. Using ApolloSettingsConfig:
            ```python
            settings = ApolloSettingsConfig(
                meta_server_address="http://localhost:8080",
                app_id="my-app"
            )
            client = AsyncApolloClient(settings=settings)
            ```

        3. Using direct parameters:
            ```python
            client = AsyncApolloClient(
                meta_server_address="http://localhost:8080",
                app_id="my-app"
            )
            ```
        """
        if settings is None and meta_server_address is None and app_id is None:
            settings = ApolloSettingsConfig()  # Will load from environment variables

        # Initialize cache directory path first
        self._cache_file_dir_path = None

        # If settings is provided, use it
        if settings is not None:
            self._meta_server_address = settings.meta_server_address
            self._app_id = settings.app_id
            self._app_secret = settings.app_secret if settings.using_app_secret else None
            self._cluster = settings.cluster
            self._timeout = settings.timeout
            self._env = settings.env
            self._cycle_time = settings.cycle_time
            self._cache_file_dir_path = settings.cache_file_dir_path
            self.ip = get_local_ip(
                settings.ip,
                hint_host=config_server_host or settings.meta_server_address,
            )
            self.label = settings.label
            self._namespaces = list(settings.namespaces)
        else:
            # Use direct parameters
            self._meta_server_address = meta_server_address
            self._app_id = app_id
            self._app_secret = app_secret
            self._cluster = cluster
            self._timeout = timeout
            self._env = env
            self._cycle_time = cycle_time
            self._cache_file_dir_path = cache_file_dir_path
            self.ip = get_local_ip(
                ip,
                hint_host=config_server_host or meta_server_address,
            )
            self.label = label if label is not None else resolve_label()
            self._namespaces = (
                list(namespaces) if namespaces is not None else [DEFAULT_NAMESPACE]
            )

        # Custom config server settings (applies regardless of settings vs direct parameters)
        self._custom_config_server_host = config_server_host
        self._custom_config_server_port = config_server_port

        # Initialize other attributes
        self._memory_cache = MemoryCache()
        self._file_cache: AsyncFileCache | None = None
        self._listeners = AsyncListenerRegistry()
        self._config_server_url = None
        self._config_server_host = None
        self._config_server_port = None
        self._config_homepage_url: str | None = None
        self._started = False
        self._ready = False
        self._autostart = autostart
        self._session = session

        self._init_caches(self._cache_file_dir_path)
        self._init_transport_stack()
        self._init_repository()

    async def start(self) -> AsyncApolloClient:
        """Discover config server, fetch namespaces, and start long-polling."""
        if self._started:
            return self
        await self._ensure_session()
        await self._initialize_config_server()
        try:
            await self._repository.sync_all()
        except Exception as exc:
            logger.warning("Initial configuration sync failed: %s", exc)
            await self.load_local_cache_file()
        self._mark_ready_if_cached()
        await self._repository.start_background()
        self._started = True
        logger.info("Apollo async client started for app_id=%s", self._app_id)
        return self

    async def stop(self) -> None:
        """Stop long-polling and close HTTP transport."""
        if self._started:
            await self._repository.stop_background()
        if hasattr(self, "_transport"):
            await self._transport.close()
        self._session = None
        self._started = False
        logger.info("Apollo async client stopped")

    def is_ready(self) -> bool:
        """Return whether at least one namespace has been loaded successfully."""
        return self._ready

    def _mark_ready_if_cached(self) -> None:
        if self._memory_cache.snapshot():
            self._ready = True

    def _init_transport_stack(self) -> None:
        custom_urls = self._build_custom_homepage_urls()
        self._transport = AiohttpTransport(
            session=self._session,
            default_timeout=float(self._timeout),
        )
        self._locator = AsyncConfigServiceLocator(
            self._transport,
            meta_server_address=self._meta_server_address,
            app_id=self._app_id,
            local_ip=self.ip,
            custom_homepage_urls=custom_urls,
            discovery_timeout=float(self._timeout),
        )
        self._api = AsyncApolloConfigApi(
            self._transport,
            app_id=self._app_id,
            app_secret=self._app_secret,
            cluster=self._cluster,
            local_ip=self.ip,
            label=self.label,
            default_timeout=float(self._timeout),
        )

    def _build_custom_homepage_urls(self) -> list[str] | None:
        if not self._custom_config_server_host:
            return None
        homepage, _, _ = build_custom_config_server_url(
            self._custom_config_server_host,
            self._custom_config_server_port,
        )
        return [homepage]

    def _apply_config_service(self, homepage_url: str) -> None:
        self._config_homepage_url = homepage_url
        self._config_server_url = homepage_url
        _, self._config_server_host, self._config_server_port = service_to_endpoint(
            ServiceInstance(home_page_url=homepage_url)
        )
        if hasattr(self, "_repository"):
            self._repository.sync_poll_homepage(homepage_url)

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session exists on the transport."""
        await self._transport.ensure_session()
        self._session = self._transport.session

    async def __aenter__(self) -> AsyncApolloClient:
        """Async context manager entry."""
        if self._autostart:
            await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Async context manager exit."""
        await self.stop()

    async def _switch_config_server_if_discovery(self, exclude: str | None = None) -> None:
        if self._custom_config_server_host:
            return
        await self.update_config_server(exclude)

    def _init_repository(self) -> None:
        self._repository = AsyncConfigRepository(
            self._api,
            self._locator,
            self._namespaces,
            hooks=AsyncRepositoryHooks(
                get_homepage=lambda: self._config_homepage_url,
                set_homepage=self._apply_config_service,
                get_cached_config=lambda ns: self._memory_cache.get(ns) or {},
                apply_config=self._repository_apply_config,
                on_namespace_fetch_error=self._repository_on_fetch_error,
                switch_config_server=self._switch_config_server_if_discovery,
            ),
            cycle_time=self._cycle_time,
            fetch_timeout=float(self._timeout),
        )

    async def _repository_apply_config(
        self, result: ConfigResult, event: ConfigChangeEvent | None
    ) -> None:
        self._memory_cache.set(result.namespace, result.configurations)
        await self._file_cache.save(
            result.namespace,
            result.configurations,
            result.release_key,
        )
        if event and event.changes:
            await self._listeners.dispatch(event)
        self._ready = True

    def add_change_listener(
        self,
        callback: Callable[[ConfigChangeEvent], Any],
        *,
        namespaces: list[str] | None = None,
        keys: list[str] | None = None,
    ) -> Subscription:
        """Register a callback invoked when configuration changes."""
        ns_set = set(namespaces) if namespaces is not None else None
        key_set = set(keys) if keys is not None else None
        return self._listeners.add(callback, namespaces=ns_set, keys=key_set)

    async def _repository_on_fetch_error(self, namespace: str, exc: Exception) -> None:
        data = await self._file_cache.load(namespace) or {}
        self._memory_cache.set(namespace, data)
        self._mark_ready_if_cached()
        logger.error(
            "Fetch apollo configuration meet error, error: %s, homepage: %s",
            exc,
            self._config_homepage_url,
        )

    def _apply_custom_config_server(self) -> None:
        if not self._custom_config_server_host:
            return
        homepage, host, port = build_custom_config_server_url(
            self._custom_config_server_host,
            self._custom_config_server_port,
        )
        self._apply_config_service(homepage)
        logger.info("Using custom config server - host: %s, port: %s", host, port)

    async def _rebuild_transport_and_repository(self) -> bool:
        """Rebuild transport stack. Returns whether background polling was running."""
        was_running = self._started
        state = self._repository.export_state() if hasattr(self, "_repository") else None
        if was_running:
            await self._repository.stop_background()
        if hasattr(self, "_transport"):
            await self._transport.close()
        self._session = None
        self._init_transport_stack()
        await self._transport.ensure_session()
        self._session = self._transport.session
        self._init_repository()
        self._repository.restore_state(state)
        if self._config_homepage_url:
            self._repository.sync_poll_homepage(self._config_homepage_url)
        return was_running

    def _init_caches(self, cache_root: str | None = None) -> None:
        if cache_root is not None:
            self._cache_file_dir_path = cache_root
        root = resolve_cache_root(self._cache_file_dir_path)
        self._cache_file_dir_path = root
        self._file_cache = AsyncFileCache(root, self._app_id, self._cluster)

    async def start_polling(self) -> None:
        """Deprecated: use ``await start()``."""
        await self._repository.start_background()

    async def stop_polling(self) -> None:
        """Deprecated: use ``await stop()``."""
        await self._repository.stop_background()

    async def update_local_file_cache(
        self, release_key: str, data: dict[str, str], namespace: str = "application"
    ) -> None:
        """Update local file cache if the release key changed."""
        await self._file_cache.save(namespace, data, release_key)

    async def get_local_file_cache(self, namespace: str = "application") -> dict[str, str]:
        """Get configuration from local file cache."""
        return await self._file_cache.load(namespace) or {}

    async def fetch_config_by_namespace(self, namespace: str = "application") -> None:
        """Fetch configuration of the namespace from apollo server."""
        if not self._config_homepage_url:
            logger.warning("Config server not initialized, loading local cache")
            await self.update_cache(namespace, await self.get_local_file_cache(namespace))
            return
        await self._repository.sync_namespace(namespace)

    async def update_cache(self, namespace: str, data: dict[str, str]) -> None:
        """Update in-memory configuration cache."""
        self._memory_cache.set(namespace, data)

    async def fetch_configuration(self) -> None:
        """Get configurations for all namespaces from apollo server."""
        try:
            await self._repository.sync_all()
        except Exception as e:
            logger.warning("Fetch configuration failed: %s", e)
            await self.load_local_cache_file()

    async def load_local_cache_file(self) -> bool:
        """Load all file cache entries into memory."""
        try:
            for namespace, data in (await self._file_cache.load_all()).items():
                self._memory_cache.set(namespace, data)
            return True
        except Exception as e:
            logger.error("Error loading local cache files: %s", e)
            return False

    async def get_service_conf(self) -> list[dict[str, object]]:
        """Get config service list from meta discovery."""
        services = await self._locator.discover()
        return [
            {
                "homepageUrl": service.home_page_url,
                "instanceId": service.instance_id,
            }
            for service in services
        ]

    async def _initialize_config_server(self) -> None:
        if self._custom_config_server_host:
            self._apply_custom_config_server()
        else:
            await self.update_config_server()

    async def update_config_server(self, exclude: str | None = None) -> str:
        """Update config server via meta discovery."""
        service = await self._locator.choose_one(exclude_homepage=exclude)
        self._apply_config_service(service.home_page_url)
        logger.info(
            "Update config server url to: %s, host: %s, port: %s",
            self._config_server_url,
            self._config_server_host,
            self._config_server_port,
        )
        return self._config_server_url or ""

    async def get_value(
        self, key: str, default_val: str | None = None, namespace: str | None = None
    ) -> str | None:
        """Get the configuration value as string.

        When ``namespace`` is omitted, searches configured namespaces in order
        and returns the first match (same precedence as Java bootstrap list).
        """
        try:
            return cache_get_value(
                self._memory_cache,
                key,
                default_val,
                namespace=namespace,
                namespaces=self._namespaces,
            )
        except Exception as exc:
            logger.error("Get key(%s) value failed, error: %s", key, exc)
            return default_val

    async def get_json_value(
        self,
        key: str,
        default_val: dict[str, object] | None = None,
        namespace: str | None = None,
    ) -> dict[str, object]:
        """Get the configuration value parsed as JSON object."""
        return cache_get_json_value(
            self._memory_cache,
            key,
            default_val,  # type: ignore[arg-type]
            namespace=namespace,
            namespaces=self._namespaces,
        )

    async def get_int(
        self,
        key: str,
        default_val: int | None = None,
        namespace: str | None = None,
    ) -> int | None:
        return cache_get_int(
            self._memory_cache,
            key,
            default_val,
            namespace=namespace,
            namespaces=self._namespaces,
        )

    async def get_bool(
        self,
        key: str,
        default_val: bool | None = None,
        namespace: str | None = None,
    ) -> bool | None:
        return cache_get_bool(
            self._memory_cache,
            key,
            default_val,
            namespace=namespace,
            namespaces=self._namespaces,
        )

    async def get_float(
        self,
        key: str,
        default_val: float | None = None,
        namespace: str | None = None,
    ) -> float | None:
        return cache_get_float(
            self._memory_cache,
            key,
            default_val,
            namespace=namespace,
            namespaces=self._namespaces,
        )

    async def get_list(
        self,
        key: str,
        default_val: list[str] | None = None,
        namespace: str | None = None,
        separator: str = ",",
    ) -> list[str]:
        return cache_get_list(
            self._memory_cache,
            key,
            default_val,
            namespace=namespace,
            namespaces=self._namespaces,
            separator=separator,
        )

    async def update_config(self, **kwargs) -> None:
        """
        Update client configuration parameters dynamically.

        Supported parameters:
            meta_server_address (str): Apollo meta server address
            app_id (str): Application ID
            app_secret (str): Application secret
            cluster (str): Cluster name
            env (str): Environment
            namespaces (List[str]): List of namespaces
            ip (str): Deploy IP for grey release
            label (str): Client label for gray release matching
            timeout (int): HTTP request timeout seconds
            cycle_time (int): Cycle time to update configuration
            cache_file_dir_path (str): Directory path to store cache files
            config_server_host (str): Custom config server host
            config_server_port (int): Custom config server port

        Example:
            await client.update_config(
                timeout=60,
                cycle_time=20,
                namespaces=["application", "redis"]
            )
        """

        # Parameter validation
        updated_params = []
        needs_server_update = False
        needs_cache_reinit = False
        needs_custom_server_apply = False
        needs_namespaces_update = False

        transport_params = {
            "meta_server_address",
            "app_id",
            "app_secret",
            "cluster",
            "ip",
            "label",
            "timeout",
            "config_server_host",
            "config_server_port",
        }

        # Handle meta_server_address update
        if "meta_server_address" in kwargs:
            new_address = kwargs["meta_server_address"]
            if not isinstance(new_address, str) or not new_address.strip():
                raise ValueError("meta_server_address must be a non-empty string")
            if new_address != self._meta_server_address:
                self._meta_server_address = new_address.rstrip("/")
                needs_server_update = True
                updated_params.append("meta_server_address")

        # Handle app_id update
        if "app_id" in kwargs:
            new_app_id = kwargs["app_id"]
            if not isinstance(new_app_id, str) or not new_app_id.strip():
                raise ValueError("app_id must be a non-empty string")
            if new_app_id != self._app_id:
                self._app_id = new_app_id
                needs_cache_reinit = True
                updated_params.append("app_id")

        # Handle app_secret update
        if "app_secret" in kwargs:
            new_secret = kwargs["app_secret"]
            if new_secret is not None and not isinstance(new_secret, str):
                raise ValueError("app_secret must be a string or None")
            if new_secret != self._app_secret:
                self._app_secret = new_secret
                updated_params.append("app_secret")

        # Handle cluster update
        if "cluster" in kwargs:
            new_cluster = kwargs["cluster"]
            if not isinstance(new_cluster, str) or not new_cluster.strip():
                raise ValueError("cluster must be a non-empty string")
            if new_cluster != self._cluster:
                self._cluster = new_cluster
                needs_cache_reinit = True
                updated_params.append("cluster")

        # Handle env update
        if "env" in kwargs:
            new_env = kwargs["env"]
            if not isinstance(new_env, str) or not new_env.strip():
                raise ValueError("env must be a non-empty string")
            if new_env != self._env:
                self._env = new_env
                updated_params.append("env")

        # Handle namespaces update
        if "namespaces" in kwargs:
            new_namespaces = kwargs["namespaces"]
            if not isinstance(new_namespaces, list) or not new_namespaces:
                raise ValueError("namespaces must be a non-empty list")
            if not all(isinstance(ns, str) and ns.strip() for ns in new_namespaces):
                raise ValueError("All namespaces must be non-empty strings")

            # Update notification map
            old_namespaces = set(self._namespaces)
            new_namespaces_set = set(new_namespaces)

            if old_namespaces != new_namespaces_set:
                self._namespaces = list(new_namespaces)
                self._repository.set_namespaces(self._namespaces)

                # Clear cache for removed namespaces
                for ns in old_namespaces - new_namespaces_set:
                    self._memory_cache.remove(ns)
                    await self._file_cache.remove(ns)

                needs_namespaces_update = True
                updated_params.append("namespaces")

        # Handle ip update
        if "ip" in kwargs:
            new_ip = kwargs["ip"]
            if new_ip is not None and not isinstance(new_ip, str):
                raise ValueError("ip must be a string or None")
            hint_host = (
                kwargs.get("config_server_host")
                or self._custom_config_server_host
                or kwargs.get("meta_server_address")
                or self._meta_server_address
            )
            new_ip_resolved = get_local_ip(new_ip, hint_host=hint_host)
            if new_ip_resolved != self.ip:
                self.ip = new_ip_resolved
                updated_params.append("ip")

        # Handle label update
        if "label" in kwargs:
            new_label = kwargs["label"]
            if new_label is not None and not isinstance(new_label, str):
                raise ValueError("label must be a string or None")
            if new_label != self.label:
                self.label = new_label
                updated_params.append("label")

        # Handle timeout update
        if "timeout" in kwargs:
            new_timeout = kwargs["timeout"]
            if not isinstance(new_timeout, int) or new_timeout <= 0:
                raise ValueError("timeout must be a positive integer")
            if new_timeout != self._timeout:
                self._timeout = new_timeout
                updated_params.append("timeout")

        # Handle cycle_time update
        if "cycle_time" in kwargs:
            new_cycle_time = kwargs["cycle_time"]
            if not isinstance(new_cycle_time, int) or new_cycle_time <= 0:
                raise ValueError("cycle_time must be a positive integer")
            if new_cycle_time != self._cycle_time:
                self._cycle_time = new_cycle_time
                self._repository.cycle_time = new_cycle_time
                updated_params.append("cycle_time")

        # Handle cache_file_dir_path update
        if "cache_file_dir_path" in kwargs:
            new_cache_path = kwargs["cache_file_dir_path"]
            if new_cache_path is not None and not isinstance(new_cache_path, str):
                raise ValueError("cache_file_dir_path must be a string or None")
            if new_cache_path != self._cache_file_dir_path:
                self._cache_file_dir_path = new_cache_path
                needs_cache_reinit = True
                updated_params.append("cache_file_dir_path")

        # Handle config_server_host update
        if "config_server_host" in kwargs:
            new_host = kwargs["config_server_host"]
            if new_host is not None and not isinstance(new_host, str):
                raise ValueError("config_server_host must be a string or None")
            if new_host != getattr(self, "_custom_config_server_host", None):
                self._custom_config_server_host = new_host
                if new_host:
                    needs_custom_server_apply = True
                    needs_server_update = False
                else:
                    needs_server_update = True
                updated_params.append("config_server_host")

        # Handle config_server_port update
        if "config_server_port" in kwargs:
            new_port = kwargs["config_server_port"]
            if new_port is not None and (not isinstance(new_port, int) or new_port <= 0):
                raise ValueError("config_server_port must be a positive integer or None")
            if new_port != getattr(self, "_custom_config_server_port", None):
                self._custom_config_server_port = new_port
                if new_port and self._custom_config_server_host:
                    needs_custom_server_apply = True
                    needs_server_update = False
                updated_params.append("config_server_port")

        # Apply changes: rebuild transport before discover/fetch when needed
        needs_transport_rebuild = bool(
            updated_params and transport_params.intersection(updated_params)
        )

        if needs_cache_reinit:
            self._init_caches(self._cache_file_dir_path)

        resume_background = False
        if needs_transport_rebuild:
            resume_background = await self._rebuild_transport_and_repository()

        if needs_custom_server_apply:
            self._apply_custom_config_server()
        elif needs_server_update:
            try:
                await self.update_config_server()
            except Exception as e:
                logger.error(f"Failed to update config server: {e}")

        needs_fetch = (
            needs_cache_reinit
            or needs_server_update
            or needs_custom_server_apply
            or needs_namespaces_update
            or needs_transport_rebuild
        )
        if needs_fetch:
            try:
                await self.fetch_configuration()
            except Exception as e:
                logger.error(f"Failed to fetch configuration after update: {e}")

        if resume_background:
            await self._repository.start_background()

        if updated_params:
            logger.info(
                f"Successfully updated Apollo client parameters: {', '.join(updated_params)}"
            )
        else:
            logger.info("No parameters were changed")

    def get_current_config(self) -> dict[str, object]:
        """
        Get current client configuration parameters.

        Returns:
            Dict containing current configuration values
        """

        return {
            "meta_server_address": self._meta_server_address,
            "app_id": self._app_id,
            "app_secret": self._app_secret,
            "cluster": self._cluster,
            "env": self._env,
            "namespaces": list(self._namespaces),
            "ip": self.ip,
            "label": self.label,
            "timeout": self._timeout,
            "cycle_time": self._cycle_time,
            "cache_file_dir_path": self._cache_file_dir_path,
            "config_server_url": self._config_server_url,
            "config_server_host": self._config_server_host,
            "config_server_port": self._config_server_port,
            "custom_config_server_host": getattr(self, "_custom_config_server_host", None),
            "custom_config_server_port": getattr(self, "_custom_config_server_port", None),
        }
