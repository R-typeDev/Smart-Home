from typing import Any

from database.integrations import (
    get_integration_settings,
    get_integration_secret,
)
from integrations.tplink_router.router import TPLinkRouterIntegration
from services.secret_service import decrypt_secret


class TPLinkRouterAdapter:
    """TP-Link router integration adapter."""

    integration_id = "tplink_router"

    def _get_client(self, device: dict[str, Any]) -> TPLinkRouterIntegration:
        instance_id = device.get("instance_id")

        if not instance_id:
            raise RuntimeError("TP-Link connection is not configured.")

        settings = get_integration_settings(instance_id)

        host = settings.get("host", {}).get("value")
        username = settings.get("username", {}).get("value")

        encrypted_password = get_integration_secret(
            instance_id,
            "password",
        )

        if not host or not username or not encrypted_password:
            raise RuntimeError("TP-Link router configuration is incomplete.")

        password = decrypt_secret(encrypted_password)

        return TPLinkRouterIntegration(
            host=host,
            username=username,
            password=password,
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
        client = self._get_client(device)

        return {
            "online": client.is_online(),
        }

    def get_dhcp_clients(
        self,
        device: dict[str, Any],
    ) -> list[dict[str, str]]:
        client = self._get_client(device)
        return client.get_dhcp_clients()

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise ValueError("TP-Link router does not support commands.")