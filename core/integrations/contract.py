from typing import Any, Protocol


class DeviceIntegration(Protocol):
    """Common contract for integrations connected to Smart Home Core."""

    integration_id: str

    def get_capabilities(
        self,
        device: dict[str, Any],
    ) -> set[str]:
        ...

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        ...

    def get_state(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...