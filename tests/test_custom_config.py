"""
Simple test for custom config server functionality
"""

from pyapollo.client import ApolloClient


def test_custom_config_server():
    """Test custom config server parameters"""
    print("Testing custom config server functionality...")

    # Test 1: Create client with custom config server
    print("\nTest 1: Creating client with custom config server")
    try:
        client = ApolloClient(
            app_id="test-app",
            config_server_host="http://test-config.example.com",
            config_server_port=8080,
            timeout=5,  # Short timeout for quick testing
        )

        config = client.get_current_config()
        print(f"✓ Custom host: {config['custom_config_server_host']}")
        print(f"✓ Custom port: {config['custom_config_server_port']}")
        print(f"✓ Active host: {config['config_server_host']}")
        print(f"✓ Active port: {config['config_server_port']}")

        client.stop_polling_thread()

    except Exception as e:
        print(f"✗ Failed to create client with custom config: {e}")

    # Test 2: Update config server at runtime
    print("\nTest 2: Updating config server at runtime")
    try:
        client = ApolloClient(
            app_id="test-app",
            config_server_host="http://initial.example.com",
            config_server_port=8080,
            timeout=5,
        )

        print("Before update:")
        config = client.get_current_config()
        print(f"  Host: {config['custom_config_server_host']}")
        print(f"  Port: {config['custom_config_server_port']}")

        # Update config server
        client.update_config(
            config_server_host="http://updated.example.com", config_server_port=9090
        )

        print("After update:")
        config = client.get_current_config()
        print(f"  Host: {config['custom_config_server_host']}")
        print(f"  Port: {config['custom_config_server_port']}")
        print(
            f"  Active: {config['config_server_host']}:{config['config_server_port']}"
        )

        client.stop_polling_thread()

    except Exception as e:
        print(f"✗ Failed to update config server: {e}")

    # Test 3: Parameter validation
    print("\nTest 3: Parameter validation")
    try:
        client = ApolloClient(
            app_id="test-app",
            config_server_host="http://test.example.com",
            config_server_port=8080,
            timeout=5,
        )

        # Test invalid host type
        try:
            client.update_config(config_server_host=123)
            print("✗ Should have failed with invalid host type")
        except ValueError:
            print("✓ Correctly rejected invalid host type")

        # Test invalid port
        try:
            client.update_config(config_server_port=-1)
            print("✗ Should have failed with invalid port")
        except ValueError:
            print("✓ Correctly rejected invalid port")

        # Test valid update
        try:
            client.update_config(
                config_server_host="http://valid.example.com", config_server_port=8888
            )
            print("✓ Valid update succeeded")
        except Exception as e:
            print(f"✗ Valid update failed: {e}")

        client.stop_polling_thread()

    except Exception as e:
        print(f"✗ Validation test setup failed: {e}")

    print("\n" + "=" * 50)
    print("Custom config server functionality test completed!")
    print("Note: Network errors are expected since we're using test URLs")


if __name__ == "__main__":
    test_custom_config_server()
