
from typing import Any, Protocol


class DeviceIntegration(Protocol):
    """Common contract for integrations connected to Smart Home Core."""

    @property
    def integration_id(self) -> str:
        """Stable identifier used by Core."""
        ...

    def get_capabilities(
        self,
        device: dict[str, Any],
    ) -> set[str]:
        """Return capabilities supported by this particular device."""
        ...

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Describe commands supported by this device."""
        ...

    def get_state(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the device state in a normalized format."""
        ...

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a supported command and return a normalized result."""
        ...
