
import os
import uuid

from fastapi import APIRouter, HTTPException

from core.database.devices import add_device, get_device, get_devices
from core.database.integrations import get_integrations
from integrations.tuya.plug import TuyaPlugIntegration

router = APIRouter()


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


@router.get("/api/devices")
def get_devices_list():
    return get_devices()


@router.get("/api/integrations")
def get_integrations_list():
    return get_integrations()


@router.post("/api/devices")
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


@router.get("/api/devices/{device_id}/status")
def get_device_status(device_id: str):
    device = get_configured_tuya_device(device_id)
    integration = get_tuya_plug_integration()
    status = get_tuya_power_status(integration)

    return {
        "device_id": device["id"],
        "name": device["name"],
        **status,
    }


@router.post("/api/devices/{device_id}/on")
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


@router.post("/api/devices/{device_id}/off")
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


@router.get("/api/devices/{device_id}")
def get_device_by_id(device_id: str):
    device = get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    return device
