"""
Apollo Client Custom Config Server Demo

This example demonstrates how to use custom config server host and port
instead of relying on meta server discovery.
"""

from pyapollo.client import ApolloClient


def example_1_direct_config_server():
    """Using direct config server without meta server"""
    print("Example 1: Direct Config Server Connection")

    # Connect directly to a known config server
    client = ApolloClient(
        app_id="my-app",
        config_server_host="http://config-server.example.com",
        config_server_port=8080,
        # No need for meta_server_address when using custom config server
    )

    config = client.get_current_config()
    print(
        f"✓ Connected directly to: {config['config_server_host']}:{config['config_server_port']}"
    )
    print(f"  Custom host: {config['custom_config_server_host']}")
    print(f"  Custom port: {config['custom_config_server_port']}")

    client.stop_polling_thread()


def example_2_update_config_server():
    """Updating config server at runtime"""
    print("\nExample 2: Runtime Config Server Update")

    # Start with meta server discovery
    client = ApolloClient(meta_server_address="http://localhost:8080", app_id="my-app")

    print("Initial config server (from meta server):")
    config = client.get_current_config()
    print(f"  Server: {config['config_server_host']}:{config['config_server_port']}")

    # Switch to direct config server
    client.update_config(
        config_server_host="http://direct-config.example.com", config_server_port=9090
    )

    print("Updated to direct config server:")
    config = client.get_current_config()
    print(f"  Server: {config['config_server_host']}:{config['config_server_port']}")
    print(f"  Custom host: {config['custom_config_server_host']}")
    print(f"  Custom port: {config['custom_config_server_port']}")

    client.stop_polling_thread()


def example_3_switch_back_to_meta_server():
    """Switching back to meta server discovery"""
    print("\nExample 3: Switch Back to Meta Server Discovery")

    # Start with direct config server
    client = ApolloClient(
        app_id="my-app",
        config_server_host="http://direct-config.example.com",
        config_server_port=9090,
        meta_server_address="http://localhost:8080",  # Keep meta server for fallback
    )

    print("Using direct config server:")
    config = client.get_current_config()
    print(f"  Server: {config['config_server_host']}:{config['config_server_port']}")
    print(f"  Using custom: {bool(config['custom_config_server_host'])}")

    # Switch back to meta server discovery by clearing custom config
    client.update_config(config_server_host=None, config_server_port=None)

    print("Switched back to meta server discovery:")
    config = client.get_current_config()
    print(f"  Server: {config['config_server_host']}:{config['config_server_port']}")
    print(f"  Using custom: {bool(config['custom_config_server_host'])}")

    client.stop_polling_thread()


def example_4_load_balancing_scenario():
    """Simulating load balancing between multiple config servers"""
    print("\nExample 4: Load Balancing Scenario")

    config_servers = [
        ("http://config1.example.com", 8080),
        ("http://config2.example.com", 8080),
        ("http://config3.example.com", 8080),
    ]

    client = ApolloClient(
        app_id="my-app",
        config_server_host=config_servers[0][0],
        config_server_port=config_servers[0][1],
    )

    print("Simulating config server rotation:")

    for i, (host, port) in enumerate(config_servers):
        print(f"\n  Switching to server {i + 1}:")

        client.update_config(config_server_host=host, config_server_port=port)

        config = client.get_current_config()
        print(
            f"    Connected to: {config['config_server_host']}:{config['config_server_port']}"
        )

        # Simulate getting configuration
        try:
            value = client.get_value("sample.key", "default_value")
            print(f"    Retrieved sample config: {value}")
        except Exception as e:
            print(f"    Connection failed: {e}")

    client.stop_polling_thread()


def example_5_error_handling():
    """Error handling for invalid config server parameters"""
    print("\nExample 5: Error Handling")

    client = ApolloClient(app_id="my-app", meta_server_address="http://localhost:8080")

    # Test invalid host
    try:
        client.update_config(config_server_host=123)  # Should be string
    except ValueError as e:
        print(f"✓ Caught invalid host type: {e}")

    # Test invalid port
    try:
        client.update_config(config_server_port=-1)  # Should be positive
    except ValueError as e:
        print(f"✓ Caught invalid port value: {e}")

    # Test invalid port type
    try:
        client.update_config(config_server_port="8080")  # Should be int
    except ValueError as e:
        print(f"✓ Caught invalid port type: {e}")

    # Valid updates should work
    try:
        client.update_config(
            config_server_host="http://valid-server.com", config_server_port=8080
        )
        print("✓ Valid config server update succeeded")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

    client.stop_polling_thread()


def example_6_production_scenario():
    """Real-world production scenario"""
    print("\nExample 6: Production Scenario")

    # Development environment - use meta server
    print("Development environment:")
    dev_client = ApolloClient(
        meta_server_address="http://dev-apollo:8080", app_id="my-app", env="DEV"
    )

    config = dev_client.get_current_config()
    print("  Using meta server discovery")
    print(
        f"  Server: {config.get('config_server_host', 'N/A')}:{config.get('config_server_port', 'N/A')}"
    )

    # Production environment - use direct config server for better performance
    print("\nProduction environment:")
    prod_client = ApolloClient(
        app_id="my-app",
        env="PROD",
        cluster="production",
        config_server_host="http://prod-config.internal.com",
        config_server_port=8080,
        # No meta server needed in production
    )

    config = prod_client.get_current_config()
    print("  Using direct config server")
    print(f"  Server: {config['config_server_host']}:{config['config_server_port']}")
    print(f"  Environment: {config['env']}")
    print(f"  Cluster: {config['cluster']}")

    dev_client.stop_polling_thread()
    prod_client.stop_polling_thread()


if __name__ == "__main__":
    print("Apollo Client Custom Config Server Examples\n" + "=" * 50)

    try:
        example_1_direct_config_server()
        example_2_update_config_server()
        example_3_switch_back_to_meta_server()
        example_4_load_balancing_scenario()
        example_5_error_handling()
        example_6_production_scenario()
    except Exception as e:
        print(f"\nNote: Some examples may fail due to network connectivity: {e}")
        print("This is expected in a demo environment.")

    print("\n" + "=" * 50)
    print("All examples completed!")
    print("\nKey benefits of custom config server:")
    print("• Bypass meta server discovery for better performance")
    print("• Direct connection to known config servers")
    print("• Support for load balancing and failover scenarios")
    print("• Reduced network hops in production environments")
    print("• Better control over service discovery")
