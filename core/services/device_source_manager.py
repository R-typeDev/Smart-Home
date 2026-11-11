
from typing import Any

from services.core_handler_registry import core_handler_registry
from services.integration_registry import integration_registry


class DeviceSourceManager:
    """Selects and calls available communication sources for devices."""

    def _is_available(self, source: dict[str, Any]) -> bool:
        if not source.get("enabled"):
            return False

        source_type = source.get("source_type")
        handler_id = source.get("handler_id")

        if source_type == "core":
            return core_handler_registry.is_registered(handler_id)

        if source_type == "integration":
            return (
                bool(source.get("connection_enabled"))
                and bool(source.get("integration_enabled"))
                and integration_registry.is_enabled(handler_id)
            )

        return False

    def get_available_sources(
        self,
        device: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if not device or not device.get("enabled"):
            return []

        sources = [
            source
            for source in device.get("sources", [])
            if self._is_available(source)
        ]

        return sorted(
            sources,
            key=lambda source: (
                source.get("priority", 100),
                0 if source.get("source_type") == "core" else 1,
                source.get("handler_id", ""),
            ),
        )

    def build_source_device(
        self,
        device: dict[str, Any],
        source: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(device)
        result.update(
            {
                "source_id": source.get("source_id"),
                "source_type": source.get("source_type"),
                "handler_id": source.get("handler_id"),
                "integration_id": source.get("integration_id"),
                "instance_id": source.get("instance_id"),
                "external_id": source.get("external_id"),
                "source_name": source.get("source_name"),
                "source": dict(source),
            }
        )
        return result

    def call(
        self,
        source: dict[str, Any],
        method: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        source_type = source.get("source_type")
        handler_id = source.get("handler_id")

        if source_type == "core":
            return core_handler_registry.call(
                handler_id,
                method,
                *args,
                **kwargs,
            )

        if source_type == "integration":
            return integration_registry.call(
                handler_id,
                method,
                *args,
                **kwargs,
            )

        raise LookupError("Unknown device source type")


device_source_manager = DeviceSourceManager()
