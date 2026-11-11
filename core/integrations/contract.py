
from typing import Any, Protocol


class DeviceIntegration(Protocol):
    """Common contract for device control integrations."""

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


class ConnectionSetupProvider(Protocol):
    """Optional contract for connection setup schemas."""

    def get_connection_setup_schema(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


class DeviceDiscoveryProvider(Protocol):
    """Optional contract for discovering devices."""

    def discover_devices(
        self,
        instance_id: str | None = None,
        **options: Any,
    ) -> list[dict[str, Any]]:
        ...


class DeviceDetailsProvider(Protocol):
    """Optional contract for retrieving device details."""

    def get_device_details(
        self,
        external_id: str,
        instance_id: str | None = None,
    ) -> dict[str, Any] | None:
        ...


class DeviceNormalizer(Protocol):
    """Optional contract for converting provider data into Core format."""

    def normalize_device(
        self,
        raw_device: dict[str, Any],
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        ...


class ConnectionTester(Protocol):
    """Optional contract for testing a connection."""

    def test_connection(
        self,
        instance_id: str,
    ) -> dict[str, Any]:
        ...


class ConnectionLifecycle(Protocol):
    """Optional contract for connection lifecycle operations."""

    def connect(
        self,
        instance_id: str,
    ) -> dict[str, Any]:
        ...

    def disconnect(
        self,
        instance_id: str,
    ) -> dict[str, Any]:
        ...

    def refresh(
        self,
        instance_id: str,
    ) -> dict[str, Any]:
        ...
