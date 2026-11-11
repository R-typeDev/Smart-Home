
from handlers.network_ping import NetworkPingHandler
from services.core_handler_registry import core_handler_registry


def register_core_handlers() -> list[str]:
    handler = NetworkPingHandler()

    if not core_handler_registry.is_registered(handler.handler_id):
        core_handler_registry.register(handler)

    return core_handler_registry.get_all_ids()
