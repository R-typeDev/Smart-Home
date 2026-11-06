
from typing import Any

from database.integrations import (
    get_integration_instance,
    get_integration_settings,
    get_integration_secret,
)
from integrations.tuya.cloud.client import TuyaCloudClient
from services.secret_service import decrypt_secret


class TuyaCloudAdapter:
    """Tuya Cloud integration adapter."""

    integration_id = "tuya_cloud"

    def _get_client(self, device: dict[str, Any]) -> TuyaCloudClient:
        instance_id = device.get("instance_id")

        if not instance_id:
            raise RuntimeError("Tuya Cloud connection is not configured.")

        instance = get_integration_instance(instance_id)

        if instance is None or instance["integration_id"] != self.integration_id:
            raise RuntimeError("Tuya Cloud connection was not found.")

        if not instance["enabled"]:
            raise RuntimeError("Tuya Cloud connection is disabled.")

        settings = get_integration_settings(instance_id)

        region = settings.get("region", {}).get("value")

        encrypted_access_id = get_integration_secret(
            instance_id,
            "access_id",
        )
        encrypted_access_secret = get_integration_secret(
            instance_id,
            "access_secret",
        )

        if not region or not encrypted_access_id or not encrypted_access_secret:
            raise RuntimeError("Tuya Cloud configuration is incomplete.")

        access_id = decrypt_secret(encrypted_access_id)
        access_secret = decrypt_secret(encrypted_access_secret)

        return TuyaCloudClient(
            access_id=access_id,
            access_secret=access_secret,
            region=region,
        )

    @staticmethod
    def _get_switch_code(device: dict[str, Any]) -> str:
        properties = device.get("properties", {})
        switch_property = properties.get("tuya_switch_code", {})

        return switch_property.get("value") or "switch_1"

    def get_capabilities(self, device: dict[str, Any]) -> set[str]:
        if device.get("type") == "smart_plug":
            return {"switch"}

        return set()

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        if device.get("type") != "smart_plug":
            return {}

        return {
            "turn_on": {"name": "Turn on"},
            "turn_off": {"name": "Turn off"},
        }

    def get_state(self, device: dict[str, Any]) -> dict[str, Any]:
        if device.get("type") != "smart_plug":
            raise ValueError("Unsupported Tuya Cloud device type.")

        client = self._get_client(device)
        external_id = device.get("external_id")

        if not external_id:
            raise RuntimeError("Tuya device ID is missing.")

        response = client.get_device_status(external_id)
        status_items = response.get("result") or []

        if isinstance(status_items, dict):
            status_items = [
                {"code": key, "value": value}
                for key, value in status_items.items()
            ]

        status = {
            item["code"]: item.get("value")
            for item in status_items
            if isinstance(item, dict) and item.get("code")
        }

        switch_code = self._get_switch_code(device)

        return {
            "online": True,
            "power": status.get(switch_code),
        }

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if device.get("type") != "smart_plug":
            raise ValueError("Unsupported Tuya Cloud device type.")

        commands = {
            "turn_on": True,
            "turn_off": False,
        }

        if command not in commands:
            raise ValueError(f"Unsupported command: {command}")

        client = self._get_client(device)
        external_id = device.get("external_id")

        if not external_id:
            raise RuntimeError("Tuya device ID is missing.")

        client.send_commands(
            device_id=external_id,
            commands=[
                {
                    "code": self._get_switch_code(device),
                    "value": commands[command],
                }
            ],
        )

        return self.get_state(device)

    def get_user_devices(
        self,
        instance_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        instance = get_integration_instance(instance_id)

        if instance is None or instance["integration_id"] != self.integration_id:
            raise RuntimeError("Tuya Cloud connection was not found.")

        settings = get_integration_settings(instance_id)
        user_id = settings.get("user_id", {}).get("value")

        if not user_id:
            raise RuntimeError("Tuya Cloud User ID is not configured.")

        client = self._get_client({
            "instance_id": instance_id,
        })

        return client.get_user_devices(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
