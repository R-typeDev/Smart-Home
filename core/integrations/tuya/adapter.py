from typing import Any

from database.connection import get_connection
from integrations.tuya.plug import TuyaPlugIntegration


class TuyaIntegrationAdapter:
    """Tuya adapter using device-specific settings."""

    integration_id = "tuya"

    def _settings(self, device: dict[str, Any]) -> dict[str, str]:
        if device.get("type") != "smart_plug":
            raise ValueError("Tuya integration only supports smart plugs.")

        device_id = device.get("id")
        external_id = device.get("external_id")

        if not device_id or not external_id:
            raise ValueError("Tuya device identifiers are missing.")

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

        required = ("plug_ip", "plug_local_key")
        missing = [
            key for key in required
            if not settings.get(key)
        ]

        if missing:
            raise RuntimeError(
                "Tuya device settings are incomplete in SQLite: "
                + ", ".join(missing)
            )

        settings.setdefault("plug_version", "3.5")
        return settings

    def _client(self, device: dict[str, Any]) -> TuyaPlugIntegration:
        settings = self._settings(device)

        return TuyaPlugIntegration(
            device_id=device["external_id"],
            ip_address=settings["plug_ip"],
            local_key=settings["plug_local_key"],
            version=settings["plug_version"],
        )

    def get_capabilities(self, device: dict[str, Any]) -> set[str]:
        self._settings(device)
        return {"switch"}

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        self._settings(device)
        return {
            "turn_on": {"parameters": {}},
            "turn_off": {"parameters": {}},
        }

    def get_state(self, device: dict[str, Any]) -> dict[str, Any]:
        result = self._client(device).get_status()
        dps = result.get("dps", {})

        return {
            "online": True,
            "power": dps.get("1"),
        }

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = self._client(device)

        if command == "turn_on":
            client.turn_on()
        elif command == "turn_off":
            client.turn_off()
        else:
            raise ValueError(
                f"Unsupported command for Tuya plug: {command}"
            )

        return self.get_state(device)