
from typing import Any

from database.integrations import (
    get_integration_instance,
    get_integration_instances,
    get_integration_settings,
    get_integration_secret,
)
from integrations.tuya.cloud.client import TUYA_REGIONS, TuyaCloudClient
from services.secret_service import decrypt_secret


class TuyaCloudAdapter:
    """Tuya Cloud integration adapter."""

    integration_id = "tuya_cloud"

    def is_configured(self, instance_id: str) -> bool:
        instance = get_integration_instance(instance_id)

        if (
            instance is None
            or instance["integration_id"] != self.integration_id
        ):
            return False

        settings = get_integration_settings(instance_id)

        region = settings.get("region", {}).get("value")
        user_id = settings.get("user_id", {}).get("value")

        access_id = get_integration_secret(instance_id, "access_id")
        access_secret = get_integration_secret(
            instance_id,
            "access_secret",
        )

        return bool(
            region in TUYA_REGIONS
            and user_id
            and access_id
            and access_secret
        )

    def get_connection_setup_schema(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        connections = get_integration_instances(self.integration_id)

        options = [
            {
                "label": item["name"],
                "value": item["id"],
            }
            for item in connections
            if item.get("enabled")
            and get_integration_secret(item["id"], "access_id")
            and get_integration_secret(item["id"], "access_secret")
        ]

        return {
            "methods": [
                {
                    "id": "cloud",
                    "name": "Tuya Cloud",
                    "description": "Connect through an existing Tuya Cloud account.",
                    "available": bool(options),
                    "fields": [
                        {
                            "name": "instance_id",
                            "label": "Cloud connection",
                            "type": "select",
                            "required": True,
                            "secret": False,
                            "options": options,
                        },
                    ],
                },
            ],
        }

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

        encrypted_access_id = get_integration_secret(instance_id, "access_id")
        encrypted_access_secret = get_integration_secret(
            instance_id,
            "access_secret",
        )

        if not region or not encrypted_access_id or not encrypted_access_secret:
            raise RuntimeError("Tuya Cloud configuration is incomplete.")

        return TuyaCloudClient(
            access_id=decrypt_secret(encrypted_access_id),
            access_secret=decrypt_secret(encrypted_access_secret),
            region=region,
        )

    def _get_user_id(self, instance_id: str) -> str:
        instance = get_integration_instance(instance_id)

        if instance is None or instance["integration_id"] != self.integration_id:
            raise RuntimeError("Tuya Cloud connection was not found.")

        settings = get_integration_settings(instance_id)
        user_id = settings.get("user_id", {}).get("value")

        if not user_id:
            raise RuntimeError("Tuya Cloud User ID is not configured.")

        return user_id

    @staticmethod
    def _get_switch_code(device: dict[str, Any]) -> str:
        properties = device.get("properties", {})
        switch_property = properties.get("tuya_switch_code", {})

        return switch_property.get("value") or "switch_1"

    @staticmethod
    def _extract_devices(response: dict[str, Any]) -> list[dict[str, Any]]:
        result = response.get("result")

        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]

        if isinstance(result, dict):
            for key in ("devices", "list", "items"):
                value = result.get(key)
                if isinstance(value, list):
                    return [
                        item for item in value
                        if isinstance(item, dict)
                    ]

        return []

    def discover_devices(
        self,
        instance_id: str | None = None,
        **options: Any,
    ) -> list[dict[str, Any]]:
        if not instance_id:
            raise ValueError("Tuya Cloud connection ID is required.")

        response = self.get_user_devices(
            instance_id=instance_id,
            page=int(options.get("page", 1)),
            page_size=int(options.get("page_size", 50)),
        )

        return self._extract_devices(response)

    def get_device_details(
        self,
        external_id: str,
        instance_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not instance_id:
            raise ValueError("Tuya Cloud connection ID is required.")

        for device in self.discover_devices(instance_id):
            if str(device.get("id", "")) == str(external_id):
                return device

        return None

    def normalize_device(
        self,
        raw_device: dict[str, Any],
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        category = raw_device.get("category")

        category_map = {
            "cz": "smart_plug",
            "dj": "light",
        }

        external_id = raw_device.get("id")

        if not external_id:
            raise ValueError("Tuya device ID is missing.")

        name = (
            raw_device.get("name")
            or raw_device.get("product_name")
            or "Tuya device"
        )

        return {
            "external_id": str(external_id),
            "instance_id": instance_id,
            "name": name,
            "category": category,
            "type": category_map.get(category, "unknown"),
            "manufacturer": raw_device.get("manufacturer"),
            "model": raw_device.get("model"),
            "product_id": raw_device.get("product_id"),
            "serial_number": raw_device.get("uuid"),
            "firmware_version": raw_device.get("firmware_version"),
            "image_url": (
                raw_device.get("icon")
                or raw_device.get("icon_url")
            ),
            "metadata": {
                key: raw_device.get(key)
                for key in (
                    "category",
                    "product_name",
                    "product_id",
                    "uuid",
                    "online",
                    "status",
                    "functions",
                    "status_range",
                )
                if raw_device.get(key) is not None
            },
        }

    def test_connection(self, instance_id: str) -> dict[str, Any]:
        try:
            user_id = self._get_user_id(instance_id)
            client = self._get_client({"instance_id": instance_id})

            response = client.get_user_devices(
                user_id=user_id,
                page=1,
                page_size=1,
            )

            if not isinstance(response, dict) or response.get("success") is False:
                return {
                    "success": False,
                    "message": "Tuya Cloud connection test failed.",
                }

            return {
                "success": True,
                "message": "Tuya Cloud connection is working.",
            }

        except Exception as error:
            return {
                "success": False,
                "message": str(error),
            }

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

        return {
            "power": status.get(self._get_switch_code(device)),
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
        user_id = self._get_user_id(instance_id)
        client = self._get_client({"instance_id": instance_id})

        return client.get_user_devices(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )
