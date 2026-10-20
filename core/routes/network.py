
from fastapi import APIRouter, HTTPException

from core.database.devices import get_device, get_devices
from integrations.tplink_router.router import TPLinkRouterIntegration

router = APIRouter()

NETWORK_DEVICE_TYPES = {"router", "access_point", "switch"}


def get_router_integration() -> TPLinkRouterIntegration:
    import os

    host = os.getenv("TPLINK_ROUTER_HOST", "http://192.168.0.1")
    username = os.getenv("TPLINK_ROUTER_USERNAME", "admin")
    password = os.getenv("TPLINK_ROUTER_PASSWORD")

    if not password:
        raise HTTPException(
            status_code=503,
            detail="Router password is not configured.",
        )

    return TPLinkRouterIntegration(
        host=host,
        username=username,
        password=password,
    )


@router.get("/api/network")
def get_network_devices():
    return [
        device
        for device in get_devices()
        if device.get("type") in NETWORK_DEVICE_TYPES
    ]


@router.get("/api/network/{device_id}")
def get_network_device(device_id: str):
    device = get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    if device.get("type") not in NETWORK_DEVICE_TYPES:
        raise HTTPException(
            status_code=404,
            detail="Network device not found.",
        )

    result = {
        "device": device,
        "online": None,
        "dhcp_clients": [],
        "integration_supported": False,
    }

    if (
        device.get("type") == "router"
        and device.get("integration_id") == "tplink_router"
    ):
        integration = get_router_integration()
        online = integration.is_online()

        result["online"] = online
        result["integration_supported"] = True

        if online:
            try:
                result["dhcp_clients"] = integration.get_dhcp_clients()
            except Exception as error:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Could not retrieve router data: "
                        f"{type(error).__name__}"
                    ),
                ) from error

    return result
