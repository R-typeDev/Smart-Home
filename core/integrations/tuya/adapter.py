from typing import Any

from database.devices import get_device_source_secret
from services.secret_service import decrypt_secret
from integrations.tuya.plug import TuyaPlugIntegration


class TuyaLocalAdapter:
    """Tuya Local integration adapter."""

    integration_id = "tuya_local"

    def _get_client(self, device: dict[str, Any]) -> TuyaPlugIntegration:
        if device.get("type") != "smart_plug":
            raise ValueError("Unsupported Tuya Local device type.")

        instance_id = device.get("instance_id")
        external_id = device.get("external_id")

        properties = device.get("properties", {})

        ip_address = properties.get("ip_address", {}).get("value")
        version = properties.get("tuya_version", {}).get("value", "3.5")

        encrypted_key = get_device_source_secret(
            device["id"],
            instance_id,
            "local_key",
        )

        if not encrypted_key:
            raise RuntimeError("Tuya Local Key is not configured.")

        local_key = decrypt_secret(encrypted_key)

        return TuyaPlugIntegration(
            device_id=external_id,
            ip_address=ip_address,
            local_key=local_key,
            version=version,
        )

    def get_capabilities(self, device: dict[str, Any]) -> set[str]:
        return {"switch"}

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        return {
            "turn_on": {"name": "Turn on"},
            "turn_off": {"name": "Turn off"},
        }

    def get_state(self, device: dict[str, Any]) -> dict[str, Any]:
        client = self._get_client(device)
        status = client.get_status()

        dps = status.get("dps", {})

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
        client = self._get_client(device)

        if command == "turn_on":
            client.turn_on()
        elif command == "turn_off":
            client.turn_off()
        else:
            raise ValueError(f"Unsupported command: {command}")

        return self.get_state(device)