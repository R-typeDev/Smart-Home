from services.integration_manager import integration_manager


def register_integrations() -> list[str]:
    """Discover and register all available integration adapters."""
    return integration_manager.discover()