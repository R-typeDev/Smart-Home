import importlib
import inspect
import logging
import pkgutil
from threading import RLock

from database.integrations import (
    get_integration,
    set_integration_enabled,
)
from integrations import __path__ as integrations_path
from services.integration_registry import integration_registry


logger = logging.getLogger(__name__)


class IntegrationManager:
    """Discovers adapters and synchronizes their runtime state with SQLite."""

    def __init__(self) -> None:
        self._lock = RLock()

    def discover(self) -> list[str]:
        discovered = []

        with self._lock:
            for module_info in pkgutil.walk_packages(
                integrations_path,
                prefix="integrations.",
            ):
                if not module_info.name.endswith(".adapter"):
                    continue

                module = importlib.import_module(module_info.name)

                for _, adapter_class in inspect.getmembers(
                    module,
                    inspect.isclass,
                ):
                    if adapter_class.__module__ != module.__name__:
                        continue

                    if not adapter_class.__name__.endswith("Adapter"):
                        continue

                    if inspect.isabstract(adapter_class):
                        continue

                    adapter = adapter_class()
                    integration_id = adapter.integration_id

                    if integration_registry.is_registered(integration_id):
                        continue

                    database_record = get_integration(integration_id)

                    if database_record is None:
                        logger.warning(
                            "No database record for integration %s",
                            integration_id,
                        )
                        continue

                    integration_registry.register(adapter)
                    discovered.append(integration_id)

                    if bool(database_record["enabled"]):
                        try:
                            integration_registry.enable(integration_id)
                        except Exception:
                            logger.exception(
                                "Could not activate integration %s",
                                integration_id,
                            )

        return discovered

    def set_enabled(
        self,
        integration_id: str,
        enabled: bool,
    ) -> dict[str, object]:
        with self._lock:
            if not integration_registry.is_registered(integration_id):
                raise LookupError(
                    f"Integration is not implemented: {integration_id}"
                )

            database_record = get_integration(integration_id)

            if database_record is None:
                raise LookupError(
                    f"Integration not found: {integration_id}"
                )

            previous_enabled = bool(database_record["enabled"])

            if enabled:
                integration_registry.enable(integration_id)

                if not set_integration_enabled(integration_id, True):
                    integration_registry.disable(integration_id)
                    raise RuntimeError(
                        "Could not save integration enabled state."
                    )
            else:
                integration_registry.disable(integration_id)

                if not set_integration_enabled(integration_id, False):
                    if previous_enabled:
                        integration_registry.enable(integration_id)

                    raise RuntimeError(
                        "Could not save integration enabled state."
                    )

            return {
                "id": integration_id,
                "enabled": enabled,
                "active": integration_registry.is_enabled(integration_id),
            }


integration_manager = IntegrationManager()
