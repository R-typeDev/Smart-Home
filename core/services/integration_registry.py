
from integrations.contract import DeviceIntegration


class IntegrationRegistry:
    """Registry for device integrations available to Core."""

    def __init__(self) -> None:
        self._integrations: dict[str, DeviceIntegration] = {}

    def register(self, integration: DeviceIntegration) -> None:
        integration_id = integration.integration_id

        if not isinstance(integration_id, str) or not integration_id.strip():
            raise ValueError("Integration ID cannot be empty.")

        if integration_id in self._integrations:
            raise ValueError(
                f"Integration already registered: {integration_id}"
            )

        self._integrations[integration_id] = integration

    def get(self, integration_id: str) -> DeviceIntegration:
        integration = self._integrations.get(integration_id)

        if integration is None:
            raise LookupError(
                f"Integration is not registered: {integration_id}"
            )

        return integration

    def get_all(self) -> list[DeviceIntegration]:
        """Return all registered integration adapters."""
        return list(self._integrations.values())

    def get_capabilities(self, device: dict) -> set[str]:
        integration_id = device.get("integration_id")

        if not integration_id:
            return set()

        integration = self.get(integration_id)
        return integration.get_capabilities(device)


integration_registry = IntegrationRegistry()
