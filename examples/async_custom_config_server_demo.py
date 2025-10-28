"""
Async Apollo Client Custom Config Server Demo

This example demonstrates how to use custom config server host and port
with the asynchronous Apollo client.
"""

import asyncio
from pyapollo.async_client import AsyncApolloClient


async def example_1_direct_async_config_server():
    """Using direct config server with async client"""
    print("Example 1: Async Direct Config Server Connection")

    # Connect directly to a known config server using async client
    async with AsyncApolloClient(
        app_id="async-test-app",
        config_server_host="http://async-config.example.com",
        config_server_port=8080,
        timeout=5,  # Short timeout for demo
    ) as client:
        config = client.get_current_config()
        print(
            f"✓ Connected directly to: {config['config_server_host']}:{config['config_server_port']}"
        )
        print(f"  Custom host: {config['custom_config_server_host']}")
        print(f"  Custom port: {config['custom_config_server_port']}")

        # Try to get a configuration value
        try:
            value = await client.get_value("test.key", "default_value", "application")
            print(f"  Retrieved test value: {value}")
        except Exception as e:
            print(
                f"  Note: Configuration retrieval expected to fail in demo: {type(e).__name__}"
            )


async def example_2_async_runtime_update():
    """Updating config server at runtime with async client"""
    print("\nExample 2: Async Runtime Config Server Update")

    try:
        # Start with meta server discovery (will likely fail in demo environment)
        async with AsyncApolloClient(
            meta_server_address="http://localhost:8080",
            app_id="async-test-app",
            timeout=2,  # Very short timeout
        ) as client:
            print("Initial config server (from meta server):")
            config = client.get_current_config()
            print(
                f"  Server: {config.get('config_server_host', 'N/A')}:{config.get('config_server_port', 'N/A')}"
            )

            # Switch to direct config server at runtime
            await client.update_config(
                config_server_host="http://async-direct.example.com",
                config_server_port=9090,
            )

            print("Updated to direct config server:")
            config = client.get_current_config()
            print(
                f"  Server: {config['config_server_host']}:{config['config_server_port']}"
            )
            print(f"  Custom host: {config['custom_config_server_host']}")
            print(f"  Custom port: {config['custom_config_server_port']}")

    except Exception as e:
        print(
            f"Note: Meta server connection expected to fail in demo: {type(e).__name__}"
        )


async def example_3_async_parameter_validation():
    """Testing parameter validation with async client"""
    print("\nExample 3: Async Parameter Validation")

    # Create a client that won't try to connect immediately
    client = AsyncApolloClient(
        app_id="validation-test",
        config_server_host="http://test.example.com",
        config_server_port=8080,
    )

    # Test valid parameter updates
    try:
        await client.update_config(
            config_server_host="http://valid-async.example.com", config_server_port=9090
        )
        print("✓ Valid async parameter update succeeded")
    except Exception as e:
        print(f"✗ Unexpected error in valid update: {e}")

    # Test invalid parameters
    try:
        await client.update_config(config_server_host=123)  # Should be string
    except ValueError as e:
        print(f"✓ Caught invalid host type: {e}")

    try:
        await client.update_config(config_server_port=-1)  # Should be positive
    except ValueError as e:
        print(f"✓ Caught invalid port value: {e}")

    try:
        await client.update_config(config_server_port="8080")  # Should be int
    except ValueError as e:
        print(f"✓ Caught invalid port type: {e}")


async def example_4_async_batch_updates():
    """Batch parameter updates with async client"""
    print("\nExample 4: Async Batch Parameter Updates")

    client = AsyncApolloClient(
        app_id="batch-test",
        config_server_host="http://initial.example.com",
        config_server_port=8080,
    )

    print("Initial configuration:")
    config = client.get_current_config()
    print(f"  Host: {config['custom_config_server_host']}")
    print(f"  Port: {config['custom_config_server_port']}")
    print(f"  Timeout: {config['timeout']}")
    print(f"  Cycle time: {config['cycle_time']}")

    # Batch update multiple parameters
    await client.update_config(
        config_server_host="http://updated-batch.example.com",
        config_server_port=9999,
        timeout=120,
        cycle_time=15,
        cluster="async-production",
    )

    print("\nAfter batch update:")
    config = client.get_current_config()
    print(f"  Host: {config['custom_config_server_host']}")
    print(f"  Port: {config['custom_config_server_port']}")
    print(f"  Timeout: {config['timeout']}")
    print(f"  Cycle time: {config['cycle_time']}")
    print(f"  Cluster: {config['cluster']}")


async def example_5_async_context_manager_pattern():
    """Proper async context manager usage"""
    print("\nExample 5: Async Context Manager Pattern")

    print("Using async context manager (recommended pattern):")

    try:
        async with AsyncApolloClient(
            app_id="context-test",
            config_server_host="http://context-config.example.com",
            config_server_port=8080,
            namespaces=["application", "async-cache"],
            timeout=5,
        ) as client:
            config = client.get_current_config()
            print("✓ Client initialized with custom config server")
            print(f"  Host: {config['config_server_host']}")
            print(f"  Port: {config['config_server_port']}")
            print(f"  Namespaces: {config['namespaces']}")

            # Update namespaces at runtime
            await client.update_config(
                namespaces=["application", "async-cache", "async-database"]
            )

            config = client.get_current_config()
            print(f"  Updated namespaces: {config['namespaces']}")

            # Try to get values from different namespaces
            for namespace in config["namespaces"]:
                try:
                    value = await client.get_value(
                        "sample.key", f"default-{namespace}", namespace
                    )
                    print(f"  {namespace}: {value}")
                except Exception:
                    print(f"  {namespace}: Expected connection error in demo")

    except Exception as e:
        print(
            f"Note: Configuration fetch expected to fail in demo environment: {type(e).__name__}"
        )


async def example_6_async_environment_switching():
    """Environment switching scenario with async client"""
    print("\nExample 6: Async Environment Switching")

    environments = {
        "dev": {
            "host": "http://dev-async-config.example.com",
            "port": 8080,
            "env": "DEV",
            "cluster": "default",
        },
        "staging": {
            "host": "http://staging-async-config.example.com",
            "port": 8080,
            "env": "STAGING",
            "cluster": "staging",
        },
        "prod": {
            "host": "http://prod-async-config.example.com",
            "port": 8080,
            "env": "PROD",
            "cluster": "production",
        },
    }

    client = AsyncApolloClient(app_id="env-switch-test", **environments["dev"])

    for env_name, env_config in environments.items():
        print(f"\nSwitching to {env_name.upper()} environment:")

        await client.update_config(
            config_server_host=env_config["host"],
            config_server_port=env_config["port"],
            env=env_config["env"],
            cluster=env_config["cluster"],
        )

        config = client.get_current_config()
        print(f"  Environment: {config['env']}")
        print(f"  Cluster: {config['cluster']}")
        print(
            f"  Config server: {config['config_server_host']}:{config['config_server_port']}"
        )


async def main():
    """Run all async examples"""
    print("Async Apollo Client Custom Config Server Examples\n" + "=" * 60)

    try:
        await example_1_direct_async_config_server()
        await example_2_async_runtime_update()
        await example_3_async_parameter_validation()
        await example_4_async_batch_updates()
        await example_5_async_context_manager_pattern()
        await example_6_async_environment_switching()

    except Exception as e:
        print(f"\nNote: Some examples may fail due to network connectivity: {e}")
        print("This is expected in a demo environment.")

    print("\n" + "=" * 60)
    print("All async examples completed!")
    print("\nKey benefits of async client with custom config server:")
    print("• Non-blocking I/O operations")
    print("• Better resource utilization in async applications")
    print("• Concurrent configuration fetching")
    print("• Seamless integration with async/await patterns")
    print("• Support for async context managers")
    print("• Thread-safe async operations with asyncio locks")


if __name__ == "__main__":
    # Run the async examples
    asyncio.run(main())
