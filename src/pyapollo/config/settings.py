"""
PyApollo settings configuration.

This module provides a configuration model for Apollo client settings using pydantic-settings.
It allows loading configuration from environment variables and .env files.
"""

import os
from typing import Any, cast

from pydantic import ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def resolve_label(explicit: str | None = None) -> str | None:
    """
    Resolve gray-release label (Java ``apollo.label`` / ``APP_LABEL``).

    Priority: explicit parameter > ``APOLLO_LABEL`` env > ``APP_LABEL`` env (Java compat).
    """
    if explicit is not None:
        return explicit or None
    return os.environ.get("APOLLO_LABEL") or os.environ.get("APP_LABEL") or None


class ApolloSettingsConfig(BaseSettings):
    """Configuration model for Apollo client settings.

    This class defines the configuration schema for Apollo client with validation.
    It supports loading configuration from:
    1. Environment variables with the prefix 'APOLLO_'
    2. .env file (either in the current directory or at a custom path)
    3. Direct initialization with parameters

    Attributes:
        meta_server_address: Apollo meta server address.
        app_id: Apollo application ID.
        using_app_secret: Flag to indicate if app_secret is required.
        app_secret: Apollo application secret key.
        cluster: Apollo cluster name.
        env: Apollo environment.
        namespaces: Apollo namespaces.
        ip: Client IP address.
        label: Client label for gray release matching (Java ``apollo.label``).
        timeout: Request timeout in seconds.
        cycle_time: Configuration refresh cycle time in seconds.
        cache_file_dir_path: Local cache file directory path.

    Environment Variables:
        Configuration can be set using environment variables with the prefix 'APOLLO_'.
        For example:
        - APOLLO_META_SERVER_ADDRESS=http://localhost:8080
        - APOLLO_APP_ID=my-app
        - APOLLO_USING_APP_SECRET=true
        - APOLLO_APP_SECRET=your-app-secret
        - APOLLO_CLUSTER=default
        - APOLLO_ENV=DEV
        - APOLLO_NAMESPACES=application,common,other  # Comma-separated list
        - APOLLO_IP=10.0.0.1
        - APOLLO_LABEL=gray-label-1
        - APOLLO_TIMEOUT=10
        - APOLLO_CYCLE_TIME=30

    .env File Example:
        You can create a .env file with the following content:
        ```
        APOLLO_META_SERVER_ADDRESS=http://localhost:8080
        APOLLO_APP_ID=my-app
        APOLLO_USING_APP_SECRET=true
        APOLLO_APP_SECRET=your-app-secret
        APOLLO_CLUSTER=default
        APOLLO_ENV=DEV
        APOLLO_NAMESPACES=application,common,other  # Comma-separated list
        APOLLO_TIMEOUT=10
        APOLLO_CYCLE_TIME=30
        ```

    Example:
        ```python
        # Load from default .env file and environment variables
        config = ApolloSettingsConfig()

        # Load from custom .env file
        config = ApolloSettingsConfig.from_env_file("/path/to/custom.env")

        # Or explicitly set values
        config = ApolloSettingsConfig(
            meta_server_address="http://localhost:8080",
            app_id="my-app",
            using_app_secret=True,
            app_secret="your-app-secret"
        )
        ```
    """

    # Required parameters
    meta_server_address: str
    app_id: str
    using_app_secret: bool = False

    # Optional parameters
    app_secret: str | None = None
    cluster: str = "default"
    env: str = "DEV"
    namespaces: str | list[str] = "application"  # Accept both string and list
    ip: str | None = None
    label: str | None = None
    timeout: int = 10
    cycle_time: int = 30
    cache_file_dir_path: str | None = None

    @field_validator("app_secret")
    @classmethod
    def validate_app_secret(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Validate app_secret based on using_app_secret flag.

        Args:
            v: The app_secret value to validate.
            info: Validation context information.

        Returns:
            The validated app_secret value.

        Raises:
            ValueError: If app_secret is required but not provided.
        """
        using_app_secret = info.data.get("using_app_secret", False)
        if using_app_secret and not v:
            raise ValueError("app_secret is required when using_app_secret is True")
        return v

    @model_validator(mode="after")
    def validate_namespaces(self) -> "ApolloSettingsConfig":
        """Convert namespaces to list format.

        This validator handles the following cases:
        1. String input (comma-separated): "app,common" -> ["app", "common"]
        2. Single string: "application" -> ["application"]
        3. List input: ["app", "common"] -> ["app", "common"]
        4. None: None -> ["application"]

        Returns:
            ApolloSettingsConfig: The validated settings instance.
        """
        if self.namespaces is None:
            self.namespaces = ["application"]
        elif isinstance(self.namespaces, str):
            # Handle both comma-separated string and single namespace
            self.namespaces = [ns.strip() for ns in self.namespaces.split(",") if ns.strip()]
        elif not isinstance(self.namespaces, list):
            raise ValueError("namespaces must be a string (comma-separated), list, or None")
        if self.label is None:
            self.label = resolve_label()
        return self

    @classmethod
    def from_env_file(
        cls: type["ApolloSettingsConfig"],
        env_file_path: str,
        **kwargs: Any,
    ) -> "ApolloSettingsConfig":
        """Create settings from a custom .env file path.

        This method allows loading configuration from a .env file at a custom location.

        Args:
            env_file_path: Path to the .env file.
            **kwargs: Additional keyword arguments to override settings.

        Returns:
            ApolloSettingsConfig: A new settings instance.

        Raises:
            FileNotFoundError: If the specified .env file doesn't exist.
            ValueError: If the .env file path is invalid.
        """
        if not os.path.isfile(env_file_path):
            raise FileNotFoundError(f"Environment file not found: {env_file_path}")

        config = SettingsConfigDict(
            env_prefix="APOLLO_",
            case_sensitive=False,
            env_file=env_file_path,
            env_file_encoding="utf-8",
        )

        # Create a new class with the custom config
        CustomSettings = type(
            "CustomApolloSettingsConfig",
            (cls,),
            {"model_config": config},
        )

        # Initialize with the custom config
        return cast("ApolloSettingsConfig", CustomSettings(**kwargs))

    model_config = SettingsConfigDict(
        env_prefix="APOLLO_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        json_schema_extra={
            "examples": [
                {
                    "meta_server_address": "http://localhost:8080",
                    "app_id": "my-app",
                    "using_app_secret": True,
                    "app_secret": "your-app-secret",
                    "cluster": "default",
                    "env": "DEV",
                    "namespaces": ["application"],
                    "timeout": 10,
                    "cycle_time": 30,
                }
            ]
        },
    )
