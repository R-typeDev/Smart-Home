
from typing import Any

from services.core_handler_registry import core_handler_registry
from services.device_source_manager import device_source_manager
from services.integration_registry import integration_registry


class DeviceService:
    """Dispatch device operations through available device sources."""

    @staticmethod
    def _get_active_sources(
        device: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not device.get("enabled"):
            raise ValueError("Device is disabled.")

        sources = device_source_manager.get_available_sources(device)

        if not sources:
            raise ValueError("Device has no available source.")

        return sources

    @staticmethod
    def _build_source_device(
        device: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any]:
        return device_source_manager.build_source_device(
            device,
            source,
        )

    @staticmethod
    def _call_source(
        source: dict[str, Any],
        method_name: str,
        source_device: dict[str, Any],
        *args: Any,
    ) -> Any:
        return device_source_manager.call(
            source,
            method_name,
            source_device,
            *args,
        )

    def get_capabilities(
        self,
        device: dict[str, Any],
    ) -> set[str]:
        sources = self._get_active_sources(device)
        capabilities: set[str] = set()
        errors = []
        successful_sources = 0

        for source in sources:
            source_device = self._build_source_device(device, source)

            try:
                result = self._call_source(
                    source,
                    "get_capabilities",
                    source_device,
                )
                capabilities.update(result or set())
                successful_sources += 1
            except Exception as error:
                errors.append(f"{source['handler_id']}: {error}")

        if successful_sources:
            return capabilities

        raise RuntimeError(
            "All device sources failed: " + "; ".join(errors)
        )

    def get_commands(
        self,
        device: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        sources = self._get_active_sources(device)
        commands: dict[str, dict[str, Any]] = {}
        errors = []
        successful_sources = 0

        for source in sources:
            source_device = self._build_source_device(device, source)

            try:
                result = self._call_source(
                    source,
                    "get_commands",
                    source_device,
                )

                for name, definition in (result or {}).items():
                    commands.setdefault(name, definition)

                successful_sources += 1
            except Exception as error:
                errors.append(f"{source['handler_id']}: {error}")

        if successful_sources:
            return commands

        raise RuntimeError(
            "All device sources failed: " + "; ".join(errors)
        )

    def get_state(
        self,
        device: dict[str, Any],
    ) -> dict[str, Any]:
        sources = self._get_active_sources(device)
        state: dict[str, Any] = {}
        errors = []
        successful_sources = 0

        for source in sources:
            source_device = self._build_source_device(device, source)

            try:
                result = self._call_source(
                    source,
                    "get_state",
                    source_device,
                )

                for name, value in (result or {}).items():
                    state.setdefault(name, value)

                successful_sources += 1
            except Exception as error:
                errors.append(f"{source['handler_id']}: {error}")

        if successful_sources:
            return state

        raise RuntimeError(
            "All device sources failed: " + "; ".join(errors)
        )

    def execute(
        self,
        device: dict[str, Any],
        command: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sources = self._get_active_sources(device)
        errors = []

        for source in sources:
            source_device = self._build_source_device(device, source)

            try:
                commands = self._call_source(
                    source,
                    "get_commands",
                    source_device,
                )

                if command not in commands:
                    continue

                return self._call_source(
                    source,
                    "execute",
                    source_device,
                    command,
                    parameters,
                )

            except Exception as error:
                errors.append(f"{source['handler_id']}: {error}")

        if errors:
            raise RuntimeError(
                "All compatible device sources failed: "
                + "; ".join(errors)
            )

        raise ValueError(f"Unsupported command: {command}")

    def get_dhcp_clients(
        self,
        device: dict[str, Any],
    ) -> list[dict[str, Any]]:
        sources = self._get_active_sources(device)
        errors = []
        compatible_sources = 0

        for source in sources:
            handler_id = source["handler_id"]

            try:
                if source["source_type"] == "core":
                    handler = core_handler_registry.get(handler_id)
                else:
                    handler = integration_registry.get(handler_id)

                if not callable(getattr(handler, "get_dhcp_clients", None)):
                    continue

                compatible_sources += 1
                source_device = self._build_source_device(device, source)

                return self._call_source(
                    source,
                    "get_dhcp_clients",
                    source_device,
                )

            except Exception as error:
                errors.append(f"{handler_id}: {error}")

        if compatible_sources and errors:
            raise RuntimeError(
                "DHCP client retrieval failed: " + "; ".join(errors)
            )

        if not compatible_sources:
            raise ValueError("No available source supports DHCP clients.")

        raise RuntimeError("Unable to retrieve DHCP clients.")


device_service = DeviceService()
