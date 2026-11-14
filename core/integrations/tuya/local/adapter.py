
from typing import Any

from database.devices import get_device_source_secret
from integrations.tuya.local.devices.plug import TuyaPlugIntegration
from services.secret_service import decrypt_secret


class TuyaLocalAdapter:
    """Tuya Local integration adapter."""

    integration_id = "tuya_local"

    @staticmethod
    def _property_value(
        properties: dict[str, Any],
        name: str,
        default: Any = None,
    ) -> Any:
        value = properties.get(name, default)

        if isinstance(value, dict):
            return value.get("value", default)

        return value if value is not None else default

    def get_connection_setup_schema(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        device_type = context.get("device_type")

        if device_type and device_type != "smart_plug":
            return {"methods": []}

        return {
            "methods": [
                {
                    "id": "local",
                    "name": "Tuya Local",
                    "description": "Direct connection over the local network.",
                    "fields": [
                        {
                            "name": "ip_address",
                            "label": "IP address",
                            "type": "text",
                            "required": True,
                            "secret": False,
                        },
                        {
                            "name": "local_key",
                            "label": "Local Key",
                            "type": "password",
                            "required": True,
                            "secret": True,
                        },
                        {
                            "name": "version",
                            "label": "Protocol version",
                            "type": "select",
                            "required": True,
                            "secret": False,
                            "default": "3.5",
                            "options": [
                                {"label": "3.3", "value": "3.3"},
                                {"label": "3.4", "value": "3.4"},
                                {"label": "3.5", "value": "3.5"},
                            ],
                        },
                    ],
                },
            ],
        }

    def _get_client(
        self,
        device: dict[str, Any],
    ) -> TuyaPlugIntegration:
        if not isinstance(device, dict):
            raise TypeError("Tuya Local requires a device object.")

        if device.get("type") != "smart_plug":
            raise ValueError("Unsupported Tuya Local device type.")

        device_id = device.get("id")
        instance_id = device.get("instance_id")
        external_id = device.get("external_id")

        if not device_id or not instance_id or not external_id:
            raise RuntimeError(
                "Tuya Local device connection data is incomplete."
            )

        properties = device.get("properties") or {}

        if not isinstance(properties, dict):
            raise RuntimeError("Device properties are invalid.")

        ip_address = self._property_value(
            properties,
            "ip_address",
        )
        version = self._property_value(
            properties,
            "tuya_version",
            "3.5",
        )

        if not ip_address:
            raise RuntimeError(
                "Tuya Local IP address is not configured."
            )

        encrypted_key = get_device_source_secret(
            device_id,
            instance_id,
            "local_key",
        )

        if not encrypted_key:
            raise RuntimeError(
                "Tuya Local Key is not configured."
            )

        return TuyaPlugIntegration(
            device_id=external_id,
            ip_address=ip_address,
            local_key=decrypt_secret(encrypted_key),
            version=str(version),
        )

    def test_connection(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            client = self._get_client(device)
            status = client.get_status()

            if not isinstance(status, dict):
                return {
                    "success": False,
                    "message": "Invalid response from Tuya Local device.",
                }

            return {
                "success": True,
                "message": "Tuya Local device is reachable.",
                "state": {
                    "online": True,
                    "power": status.get("dps", {}).get("1"),
                },
            }

        except Exception as error:
            return {
                "success": False,
                "message": str(error),
            }

    def normalize_device(
        self,
        raw_device: dict[str, Any],
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        external_id = (
            raw_device.get("id")
            or raw_device.get("device_id")
        )

        if not external_id:
            raise ValueError("Tuya Local device ID is missing.")

        return {
            "external_id": str(external_id),
            "instance_id": instance_id,
            "name": (
                raw_device.get("name")
                or raw_device.get("product_name")
                or "Tuya device"
            ),
            "category": raw_device.get("category"),
            "type": raw_device.get("type", "smart_plug"),
            "manufacturer": raw_device.get("manufacturer"),
            "model": raw_device.get("model"),
            "product_id": raw_device.get("product_id"),
            "serial_number": raw_device.get("uuid"),
            "image_url": raw_device.get("image_url"),
            "metadata": {
                key: raw_device.get(key)
                for key in (
                    "category",
                    "product_id",
                    "uuid",
                    "version",
                )
                if raw_device.get(key) is not None
            },
        }

    def get_capabilities(
        self,
        device: dict[str, Any],
    ) -> set[str]:
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

    def get_state(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any]:
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
            raise ValueError(
                f"Unsupported command: {command}"
            )

        return self.get_state(device)
