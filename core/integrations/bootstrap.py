from integrations.tuya.adapter import TuyaIntegrationAdapter
from integrations.tplink_router.adapter import TPLinkRouterAdapter
from services.integration_registry import integration_registry


def register_integrations() -> None:
    """Register available integrations with Core."""
    integration_registry.register(TuyaIntegrationAdapter())
    integration_registry.register(TPLinkRouterAdapter())