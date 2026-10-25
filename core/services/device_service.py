
from typing import Any

from services.integration_registry import integration_registry


class DeviceService:
    """Dispatch device operations through registered integrations."""

    def get_capabilities(self, device: dict[str, Any]) -> set[str]:
        return integration_registry.get_capabilities(device)

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        integration = integration_registry.get(device["integration_id"])
        return integration.get_commands(device)

    def get_state(self, device: dict[str, Any]) -> dict[str, Any]:
        integration = integration_registry.get(device["integration_id"])
        return integration.get_state(device)

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        integration = integration_registry.get(device["integration_id"])
        commands = integration.get_commands(device)

        if command not in commands:
            raise ValueError(f"Unsupported command: {command}")

        return integration.execute(device, command, parameters)


device_service = DeviceService()
