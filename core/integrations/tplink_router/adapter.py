
from typing import Any

from database.connection import get_connection
from integrations.tplink_router.router import TPLinkRouterIntegration


class TPLinkRouterAdapter:
    """TP-Link router adapter using device-specific settings."""

    integration_id = "tplink_router"

    def _settings(self, device: dict[str, Any]) -> dict[str, str]:
        if device.get("type") != "router":
            raise ValueError("This integration only supports routers.")

        device_id = device.get("id")
        if not device_id:
            raise RuntimeError("Router has no device UUID.")

        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT setting_key, setting_value
                FROM integration_settings
                WHERE device_id = ?
                  AND integration_id = ?
                """,
                (device_id, self.integration_id),
            ).fetchall()

        settings = {
            row["setting_key"]: row["setting_value"]
            for row in rows
            if row["setting_value"] is not None
        }

        required = ("host", "username", "password")
        missing = [
            key for key in required
            if not settings.get(key)
        ]

        if missing:
            raise RuntimeError(
                "TP-Link settings are incomplete in SQLite: "
                + ", ".join(missing)
            )

        return settings

    def _client(
        self,
        device: dict[str, Any],
    ) -> TPLinkRouterIntegration:
        settings = self._settings(device)

        return TPLinkRouterIntegration(
            host=settings["host"],
            username=settings["username"],
            password=settings["password"],
        )

    def get_capabilities(self, device: dict[str, Any]) -> set[str]:
        if device.get("type") != "router":
            return set()

        return {"network_status", "dhcp_clients"}

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        return {}

    def get_state(self, device: dict[str, Any]) -> dict[str, Any]:
        client = self._client(device)

        return {
            "online": client.is_online(),
        }

    def get_dhcp_clients(
        self,
        device: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._client(device).get_dhcp_clients()

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise ValueError(
            f"Unsupported router command: {command}"
        )
