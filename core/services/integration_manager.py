import importlib
import inspect
import pkgutil

from integrations import __path__ as integrations_path
from services.integration_registry import integration_registry


class IntegrationManager:
    """Discovers and registers integration adapters automatically."""

    def discover(self) -> list[str]:
        discovered = []

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

                integration_registry.register(adapter)
                discovered.append(integration_id)

        return discovered


integration_manager = IntegrationManager()