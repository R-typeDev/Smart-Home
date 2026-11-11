
from typing import Any

from network.ping import ping


class NetworkPingHandler:
    handler_id = "network_ping"

    def get_capabilities(self, device: dict[str, Any]) -> set[str]:
        return {"network_status"} if self._get_host(device) else set()

    def get_commands(self, device: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {}

    def get_state(self, device: dict[str, Any]) -> dict[str, Any]:
        host = self._get_host(device)

        if not host:
            return {}

        return {"online": ping(host)}

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise ValueError(f"Unsupported Core command: {command}")

    @staticmethod
    def _get_host(device: dict[str, Any]) -> str | None:
        properties = device.get("properties") or {}

        for key in ("ip_address", "host", "hostname"):
            value = properties.get(key)

            if isinstance(value, dict):
                value = value.get("value")

            if value:
                return str(value)

            value = device.get(key)

            if value:
                return str(value)

        return None
