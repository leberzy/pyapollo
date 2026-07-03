"""Demo: configuration change listener (pyapollo 1.0)."""

from pyapollo import ApolloClient


def on_change(event) -> None:
    for key, change in event.changes.items():
        print(
            f"[{event.namespace}] {key}: "
            f"{change.change_type.value} {change.old_value!r} -> {change.new_value!r}"
        )


def main() -> None:
    # 直连 Config Server 或 Meta 发现均可；此处演示直连
    with ApolloClient(
        app_id="arch-service-diagnose",
        config_server_host="http://testapollo.shebao.net",
        config_server_port=8080,
        namespaces=["application", "prompt"],
        cycle_time=300,
    ) as client:
        if not client.is_ready():
            print("Client not ready yet")
            return

        sub = client.add_change_listener(on_change, namespaces=["application"])
        print("Listening for changes on 'application' (Ctrl+C to exit)...")
        print("Sample value:", client.get_value("your-key", default="(not set)"))
        sub.cancel()


if __name__ == "__main__":
    main()
