from typing import Any, Protocol


class DeviceIntegration(Protocol):
    @property
    def integration_id(self) -> str: ...

    def get_capabilities(self, device: dict[str, Any]) -> set[str]: ...

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]: ...

    def get_state(self, device: dict[str, Any]) -> dict[str, Any]: ...

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class IntegrationRegistry:
    """Registry of available integration modules."""

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

    def unregister(self, integration_id: str) -> bool:
        return self._integrations.pop(integration_id, None) is not None

    def get(self, integration_id: str) -> DeviceIntegration:
        integration = self._integrations.get(integration_id)

        if integration is None:
            raise LookupError(
                f"Integration is not registered: {integration_id}"
            )

        return integration

    def get_all(self) -> list[DeviceIntegration]:
        return list(self._integrations.values())

    def get_all_ids(self) -> list[str]:
        return sorted(self._integrations)

    def is_registered(self, integration_id: str) -> bool:
        return integration_id in self._integrations


integration_registry = IntegrationRegistry()