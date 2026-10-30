from typing import Any

from services.integration_registry import integration_registry


class DeviceService:
    """Dispatch device operations through the active device source."""

    @staticmethod
    def _get_active_source(device: dict[str, Any]) -> dict[str, Any]:
        if not device.get("enabled"):
            raise ValueError("Device is disabled.")

        sources = device.get("sources", [])

        active_sources = [
            source
            for source in sources
            if source.get("enabled")
            and source.get("connection_enabled")
            and source.get("integration_enabled")
        ]

        active_sources.sort(
            key=lambda source: (
                source.get("priority", 100),
                source.get("integration_name", ""),
                source.get("connection_name", ""),
            )
        )

        if not active_sources:
            raise ValueError("Device has no enabled integration source.")

        return active_sources[0]

    def _get_integration_device(
        self,
        device: dict[str, Any],
    ) -> tuple[Any, dict[str, Any]]:
        source = self._get_active_source(device)

        integration = integration_registry.get(source["integration_id"])

        integration_device = {
            **device,
            "integration_id": source["integration_id"],
            "instance_id": source["instance_id"],
            "external_id": source["external_id"],
            "source_name": source.get("source_name"),
            "source": source,
        }

        return integration, integration_device

    def get_capabilities(self, device: dict[str, Any]) -> set[str]:
        integration, integration_device = self._get_integration_device(device)
        return integration.get_capabilities(integration_device)

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        integration, integration_device = self._get_integration_device(device)
        return integration.get_commands(integration_device)

    def get_state(self, device: dict[str, Any]) -> dict[str, Any]:
        integration, integration_device = self._get_integration_device(device)
        return integration.get_state(integration_device)

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        integration, integration_device = self._get_integration_device(device)
        commands = integration.get_commands(integration_device)

        if command not in commands:
            raise ValueError(f"Unsupported command: {command}")

        return integration.execute(
            integration_device,
            command,
            parameters,
        )

    def get_dhcp_clients(
        self,
        device: dict[str, Any],
    ) -> list[dict[str, Any]]:
        integration, integration_device = self._get_integration_device(device)

        get_clients = getattr(integration, "get_dhcp_clients", None)

        if not callable(get_clients):
            raise ValueError(
                "This device does not support retrieving connected clients."
            )

        return get_clients(integration_device)


device_service = DeviceService()