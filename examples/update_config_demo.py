"""
Apollo Client Configuration Update Demo

This example demonstrates how to dynamically update Apollo client configuration
parameters during runtime using the new update_config method.
"""

from pyapollo.client import ApolloClient


def main():
    # Initialize Apollo client with basic configuration
    print("=== Apollo Client Configuration Update Demo ===\n")

    client = ApolloClient(
        meta_server_address="http://localhost:8080",
        app_id="demo-app",
        cluster="default",
        env="DEV",
        namespaces=["application"],
        timeout=30,
        cycle_time=60,
    )

    # Display initial configuration
    print("1. Initial Configuration:")
    config = client.get_current_config()
    for key, value in config.items():
        print(f"   {key}: {value}")

    print("\n" + "=" * 50 + "\n")

    # Example 1: Update timeout and cycle_time
    print("2. Updating timeout and cycle_time...")
    try:
        client.update_config(timeout=60, cycle_time=30)
        print("   ✓ Successfully updated timeout and cycle_time")
    except Exception as e:
        print(f"   ✗ Error updating configuration: {e}")

    # Display updated configuration
    print("\n   Updated configuration:")
    config = client.get_current_config()
    print(f"   timeout: {config['timeout']}")
    print(f"   cycle_time: {config['cycle_time']}")

    print("\n" + "=" * 50 + "\n")

    # Example 2: Update namespaces
    print("3. Adding new namespaces...")
    try:
        client.update_config(namespaces=["application", "redis", "database"])
        print("   ✓ Successfully updated namespaces")
    except Exception as e:
        print(f"   ✗ Error updating namespaces: {e}")

    # Display updated namespaces
    print("\n   Updated namespaces:")
    config = client.get_current_config()
    print(f"   namespaces: {config['namespaces']}")

    print("\n" + "=" * 50 + "\n")

    # Example 3: Update application information
    print("4. Updating app information...")
    try:
        client.update_config(app_id="new-demo-app", cluster="production", env="PROD")
        print("   ✓ Successfully updated app information")
    except Exception as e:
        print(f"   ✗ Error updating app information: {e}")

    # Display updated app information
    print("\n   Updated app information:")
    config = client.get_current_config()
    print(f"   app_id: {config['app_id']}")
    print(f"   cluster: {config['cluster']}")
    print(f"   env: {config['env']}")

    print("\n" + "=" * 50 + "\n")

    # Example 4: Update with app secret
    print("5. Adding app secret...")
    try:
        client.update_config(app_secret="your-app-secret-here")
        print("   ✓ Successfully added app secret")
    except Exception as e:
        print(f"   ✗ Error adding app secret: {e}")

    print("\n" + "=" * 50 + "\n")

    # Example 5: Error handling - invalid parameters
    print("6. Testing error handling with invalid parameters...")

    try:
        client.update_config(timeout=-1)
        print("   ✗ This should have failed!")
    except ValueError as e:
        print(f"   ✓ Correctly caught invalid timeout: {e}")

    try:
        client.update_config(namespaces=[])
        print("   ✗ This should have failed!")
    except ValueError as e:
        print(f"   ✓ Correctly caught empty namespaces: {e}")

    try:
        client.update_config(app_id="")
        print("   ✗ This should have failed!")
    except ValueError as e:
        print(f"   ✓ Correctly caught empty app_id: {e}")

    print("\n" + "=" * 50 + "\n")

    # Example 6: Batch update multiple parameters
    print("7. Batch updating multiple parameters...")
    try:
        client.update_config(
            timeout=45,
            cycle_time=20,
            cluster="staging",
            namespaces=["application", "cache"],
            ip="192.168.1.100",
        )
        print("   ✓ Successfully batch updated multiple parameters")
    except Exception as e:
        print(f"   ✗ Error in batch update: {e}")

    # Display final configuration
    print("\n   Final configuration:")
    config = client.get_current_config()
    for key, value in config.items():
        print(f"   {key}: {value}")

    print("\n" + "=" * 50 + "\n")
    print("Demo completed! The client configuration has been updated successfully.")

    # Test getting a configuration value
    print("\n8. Testing configuration retrieval...")
    try:
        value = client.get_value("test.key", "default_value", "application")
        print(f"   Retrieved value for 'test.key': {value}")
    except Exception as e:
        print(f"   Error retrieving configuration: {e}")

    # Stop the polling thread
    print("\n9. Stopping Apollo client...")
    client.stop_polling_thread()
    print("   ✓ Apollo client stopped")


if __name__ == "__main__":
    main()
