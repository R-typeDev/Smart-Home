
from threading import RLock
from typing import Any

from integrations.contract import DeviceIntegration


class IntegrationRegistry:
    """Stores discovered adapters and controls their runtime availability."""

    def __init__(self) -> None:
        self._integrations: dict[str, DeviceIntegration] = {}
        self._active: set[str] = set()
        self._lock = RLock()

    def register(self, integration: DeviceIntegration) -> None:
        integration_id = integration.integration_id

        if not isinstance(integration_id, str) or not integration_id.strip():
            raise ValueError("Integration ID cannot be empty.")

        with self._lock:
            if integration_id in self._integrations:
                raise ValueError(
                    f"Integration already registered: {integration_id}"
                )

            self._integrations[integration_id] = integration

    def unregister(self, integration_id: str) -> bool:
        with self._lock:
            if integration_id not in self._integrations:
                return False

            self.disable(integration_id)
            self._integrations.pop(integration_id, None)
            return True

    def enable(self, integration_id: str) -> None:
        with self._lock:
            integration = self._integrations.get(integration_id)

            if integration is None:
                raise LookupError(
                    f"Integration is not implemented: {integration_id}"
                )

            if integration_id in self._active:
                return

            start = getattr(integration, "start", None)

            if callable(start):
                start()

            self._active.add(integration_id)

    def disable(self, integration_id: str) -> None:
        with self._lock:
            integration = self._integrations.get(integration_id)

            if integration is None:
                raise LookupError(
                    f"Integration is not registered: {integration_id}"
                )

            if integration_id not in self._active:
                return

            self._active.remove(integration_id)

            stop = getattr(integration, "stop", None)

            if callable(stop):
                stop()

    def get(self, integration_id: str) -> DeviceIntegration:
        with self._lock:
            integration = self._integrations.get(integration_id)

            if integration is None:
                raise LookupError(
                    f"Integration is not registered: {integration_id}"
                )

            if integration_id not in self._active:
                raise LookupError(
                    f"Integration is disabled: {integration_id}"
                )

            return integration

    def get_registered(self, integration_id: str) -> DeviceIntegration:
        """Return a registered adapter regardless of its enabled state."""
        with self._lock:
            integration = self._integrations.get(integration_id)

            if integration is None:
                raise LookupError(
                    f"Integration is not registered: {integration_id}"
                )

            return integration

    def get_connection_setup_schema(
        self,
        integration_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get setup fields without requiring the integration to be enabled."""
        with self._lock:
            integration = self._integrations.get(integration_id)

            if integration is None:
                raise LookupError(
                    f"Integration is not registered: {integration_id}"
                )

            provider = getattr(
                integration,
                "get_connection_setup_schema",
                None,
            )

            if not callable(provider):
                return {
                    "integration_id": integration_id,
                    "supported": False,
                    "methods": [],
                }

            schema = provider(context or {})

            if not isinstance(schema, dict):
                raise TypeError(
                    "Connection setup schema must be a dictionary."
                )

            return {
                "integration_id": integration_id,
                "supported": True,
                **schema,
            }

    def call(
        self,
        integration_id: str,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Run an adapter operation without racing against disable()."""
        with self._lock:
            integration = self.get(integration_id)
            method = getattr(integration, method_name, None)

            if not callable(method):
                raise AttributeError(
                    f"Integration does not support {method_name}."
                )

            return method(*args, **kwargs)

    def get_all(self) -> list[DeviceIntegration]:
        with self._lock:
            return list(self._integrations.values())

    def get_all_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._integrations)

    def is_registered(self, integration_id: str) -> bool:
        with self._lock:
            return integration_id in self._integrations

    def is_enabled(self, integration_id: str) -> bool:
        with self._lock:
            return integration_id in self._active


integration_registry = IntegrationRegistry()
