
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from core.database.devices import add_device, get_device, get_devices
from core.database.integrations import get_integrations
from integrations.tplink_router.router import TPLinkRouterIntegration
from integrations.tuya.plug import TuyaPlugIntegration


BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

load_dotenv(BASE_DIR / ".env")

app = FastAPI(
    title="Smart Home API",
    description="API for the Smart Home platform",
    version="0.1.0",
)


def get_router_integration() -> TPLinkRouterIntegration:
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


def get_tuya_plug_integration() -> TuyaPlugIntegration:
    try:
        return TuyaPlugIntegration()
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


def get_configured_tuya_device(device_id: str) -> dict:
    device = get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    if device["enabled"] != 1:
        raise HTTPException(status_code=409, detail="Device is disabled.")

    if device["integration_id"] != "tuya":
        raise HTTPException(
            status_code=409,
            detail="Device is not assigned to the Tuya integration.",
        )

    configured_external_id = os.getenv("TUYA_PLUG_ID")

    if not configured_external_id:
        raise HTTPException(
            status_code=503,
            detail="Tuya plug ID is not configured.",
        )

    if device["external_id"] != configured_external_id:
        raise HTTPException(
            status_code=409,
            detail="Device ID does not match the configured Tuya plug.",
        )

    return device


def get_tuya_power_status(integration: TuyaPlugIntegration) -> dict:
    try:
        result = integration.get_status()
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve smart plug status: {type(error).__name__}",
        ) from error

    dps = result.get("dps", {})

    return {
        "online": True,
        "power": dps.get("1"),
    }


@app.get("/")
def root():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/pages/network/")
def network_page():
    return FileResponse(WEB_DIR / "pages" / "network.html")


@app.get("/pages/devices/")
def devices_page():
    return FileResponse(WEB_DIR / "pages" / "devices.html")


@app.get("/pages/devices/item/{device_id}/")
def device_detail_page(device_id: str):
    return FileResponse(WEB_DIR / "pages" / "devices" / "device.html")


@app.get("/pages/network/router/")
def router_page():
    return FileResponse(WEB_DIR / "pages" / "network" / "router.html")


@app.get("/api/network/router")
def get_router_status():
    integration = get_router_integration()
    is_online = integration.is_online()

    result = {
        "online": is_online,
        "dhcp_clients": [],
    }

    if is_online:
        try:
            result["dhcp_clients"] = integration.get_dhcp_clients()
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=f"Could not retrieve router data: {type(error).__name__}",
            ) from error

    return result


@app.get("/api/devices")
def get_devices_list():
    return get_devices()


@app.get("/api/integrations")
def get_integrations_list():
    return get_integrations()


@app.post("/api/devices")
def create_device(device: dict):
    required_fields = ("name", "type")

    if not all(
        isinstance(device.get(field), str) and device[field].strip()
        for field in required_fields
    ):
        raise HTTPException(
            status_code=422,
            detail="Device name and type are required.",
        )

    device_id = str(uuid.uuid4())

    success = add_device(
        device_id=device_id,
        name=device["name"],
        device_type=device["type"],
        manufacturer=device.get("manufacturer"),
        model=device.get("model"),
        integration_id=device.get("integration_id"),
        external_id=device.get("external_id"),
        room_id=device.get("room_id"),
    )

    if not success:
        raise HTTPException(
            status_code=409,
            detail="Could not add device. Check its ID and integration.",
        )

    return {
        "success": True,
        "device": get_device(device_id),
    }


@app.get("/api/devices/{device_id}/status")
def get_device_status(device_id: str):
    device = get_configured_tuya_device(device_id)
    integration = get_tuya_plug_integration()
    status = get_tuya_power_status(integration)

    return {
        "device_id": device["id"],
        "name": device["name"],
        **status,
    }


@app.post("/api/devices/{device_id}/on")
def turn_on_device(device_id: str):
    get_configured_tuya_device(device_id)
    integration = get_tuya_plug_integration()

    try:
        integration.turn_on()
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not turn on smart plug: {type(error).__name__}",
        ) from error

    return get_tuya_power_status(integration)


@app.post("/api/devices/{device_id}/off")
def turn_off_device(device_id: str):
    get_configured_tuya_device(device_id)
    integration = get_tuya_plug_integration()

    try:
        integration.turn_off()
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not turn off smart plug: {type(error).__name__}",
        ) from error

    return get_tuya_power_status(integration)


@app.get("/api/devices/{device_id}")
def get_device_by_id(device_id: str):
    device = get_device(device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found.",
        )

    return device
