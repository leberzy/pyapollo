"""
Apollo Client Update Config - Simple Usage Examples

This file shows common scenarios for updating Apollo client configuration.
"""

from pyapollo.client import ApolloClient


def example_1_basic_usage():
    """Basic usage of update_config method"""
    print("Example 1: Basic Configuration Update")

    # Initialize client
    client = ApolloClient(
        meta_server_address="http://localhost:8080", app_id="my-app", timeout=30
    )

    # Update timeout
    client.update_config(timeout=60)
    print("✓ Updated timeout to 60 seconds")

    # Update multiple parameters at once
    client.update_config(cycle_time=20, cluster="production")
    print("✓ Updated cycle_time and cluster")

    client.stop_polling_thread()


def example_2_namespace_management():
    """Managing namespaces dynamically"""
    print("\nExample 2: Dynamic Namespace Management")

    client = ApolloClient(
        meta_server_address="http://localhost:8080",
        app_id="my-app",
        namespaces=["application"],
    )

    # Add more namespaces
    client.update_config(
        namespaces=["application", "redis", "database", "feature-flags"]
    )
    print("✓ Added additional namespaces")

    # Get current namespaces
    config = client.get_current_config()
    print(f"Current namespaces: {config['namespaces']}")

    client.stop_polling_thread()


def example_3_environment_switching():
    """Switching between different environments"""
    print("\nExample 3: Environment Switching")

    client = ApolloClient(
        meta_server_address="http://dev-apollo:8080",
        app_id="my-app",
        env="DEV",
        cluster="default",
    )

    # Switch to production
    client.update_config(
        meta_server_address="http://prod-apollo:8080", env="PROD", cluster="production"
    )
    print("✓ Switched to production environment")

    # Switch back to staging for testing
    client.update_config(
        meta_server_address="http://staging-apollo:8080",
        env="STAGING",
        cluster="staging",
    )
    print("✓ Switched to staging environment")

    client.stop_polling_thread()


def example_4_security_config():
    """Adding security configuration"""
    print("\nExample 4: Security Configuration")

    client = ApolloClient(
        meta_server_address="http://localhost:8080", app_id="secure-app"
    )

    # Add app secret for authentication
    client.update_config(app_secret="your-secret-key")
    print("✓ Added app secret for authentication")

    # Update IP for gray release
    client.update_config(ip="192.168.1.100")
    print("✓ Set specific IP for gray release")

    client.stop_polling_thread()


def example_5_performance_tuning():
    """Performance related configuration updates"""
    print("\nExample 5: Performance Tuning")

    client = ApolloClient(meta_server_address="http://localhost:8080", app_id="my-app")

    # Tune for high-frequency updates
    client.update_config(
        timeout=120,  # Longer timeout for stability
        cycle_time=10,  # More frequent polling
    )
    print("✓ Configured for high-frequency updates")

    # Later, tune for low-frequency updates to save resources
    client.update_config(
        timeout=30,  # Shorter timeout
        cycle_time=300,  # Less frequent polling (5 minutes)
    )
    print("✓ Configured for resource conservation")

    client.stop_polling_thread()


def example_6_error_handling():
    """Proper error handling when updating configuration"""
    print("\nExample 6: Error Handling")

    client = ApolloClient(meta_server_address="http://localhost:8080", app_id="my-app")

    try:
        # This will raise ValueError
        client.update_config(timeout=-10)
    except ValueError as e:
        print(f"✓ Caught validation error: {e}")

    try:
        # This will raise ValueError
        client.update_config(namespaces=[])
    except ValueError as e:
        print(f"✓ Caught validation error: {e}")

    try:
        # This should work fine
        client.update_config(timeout=45)
        print("✓ Valid update succeeded")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

    client.stop_polling_thread()


def example_7_configuration_inspection():
    """Inspecting current configuration"""
    print("\nExample 7: Configuration Inspection")

    client = ApolloClient(
        meta_server_address="http://localhost:8080",
        app_id="my-app",
        namespaces=["application", "cache"],
    )

    # Get and display current configuration
    config = client.get_current_config()
    print("Current configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    # Update some settings
    client.update_config(timeout=90, namespaces=["application", "cache", "database"])

    # Check what changed
    new_config = client.get_current_config()
    print(f"\nUpdated timeout: {new_config['timeout']}")
    print(f"Updated namespaces: {new_config['namespaces']}")

    client.stop_polling_thread()


if __name__ == "__main__":
    print("Apollo Client Configuration Update Examples\n" + "=" * 50)

    # Run all examples
    example_1_basic_usage()
    example_2_namespace_management()
    example_3_environment_switching()
    example_4_security_config()
    example_5_performance_tuning()
    example_6_error_handling()
    example_7_configuration_inspection()

    print("\n" + "=" * 50)
    print("All examples completed successfully!")
