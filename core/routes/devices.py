import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from database.devices import add_device, get_device, get_devices
from database.integrations import get_integrations, get_integration_instance
from services.device_service import device_service


router = APIRouter()


def get_enabled_device(device_id: str) -> dict[str, Any]:
    device = get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    if not device["enabled"]:
        raise HTTPException(status_code=409, detail="Device is disabled.")

    return device


def _handle_device_error(error: Exception) -> HTTPException:
    if isinstance(error, LookupError):
        return HTTPException(
            status_code=503,
            detail="Device integration is not available.",
        )

    if isinstance(error, ValueError):
        return HTTPException(status_code=409, detail=str(error))

    if isinstance(error, RuntimeError):
        return HTTPException(status_code=503, detail=str(error))

    return HTTPException(
        status_code=502,
        detail=f"Device operation failed: {type(error).__name__}",
    )


@router.get("/api/devices")
def get_devices_list():
    return get_devices()


@router.post("/api/devices")
def create_device(device: dict[str, Any]):
    name = device.get("name")
    device_type = device.get("type")

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=422, detail="Device name is required.")

    if not isinstance(device_type, str) or not device_type.strip():
        raise HTTPException(status_code=422, detail="Device type is required.")

    device_id = str(uuid.uuid4())

    try:
        created = add_device(
            device_id=device_id,
            name=name,
            device_type=device_type,
            manufacturer=device.get("manufacturer"),
            model=device.get("model"),
            room_id=device.get("room_id"),
            display_code=device.get("display_code"),
            enabled=device.get("enabled", True),
        )

        instance_id = device.get("instance_id")
        external_id = device.get("external_id")

        if instance_id or external_id:
            if not instance_id or not external_id:
                raise ValueError(
                    "Both integration connection and external device ID are required."
                )

            instance = get_integration_instance(instance_id)

            if instance is None:
                raise ValueError("Integration connection not found.")

            from database.devices import add_device_source

            add_device_source(
                device_id=created["id"],
                instance_id=instance_id,
                external_id=external_id,
                source_name=device.get("source_name"),
                enabled=device.get("source_enabled", True),
                priority=device.get("priority", 100),
            )

        return {
            "success": True,
            "device": get_device(created["id"]),
        }

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/api/devices/{device_id}")
def get_device_by_id(device_id: str):
    device = get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    return device


@router.get("/api/devices/{device_id}/capabilities")
def get_device_capabilities_route(device_id: str):
    device = get_enabled_device(device_id)

    try:
        capabilities = device_service.get_capabilities(device)
        return {
            "device_id": device["id"],
            "capabilities": sorted(capabilities),
        }
    except Exception as error:
        raise _handle_device_error(error) from error


@router.get("/api/devices/{device_id}/commands")
def get_device_commands_route(device_id: str):
    device = get_enabled_device(device_id)

    try:
        return {
            "device_id": device["id"],
            "commands": device_service.get_commands(device),
        }
    except Exception as error:
        raise _handle_device_error(error) from error


@router.get("/api/devices/{device_id}/state")
def get_device_state_route(device_id: str):
    device = get_enabled_device(device_id)

    try:
        return {
            "device_id": device["id"],
            "name": device["name"],
            **device_service.get_state(device),
        }
    except Exception as error:
        raise _handle_device_error(error) from error


@router.post("/api/devices/{device_id}/commands/{command}")
def execute_device_command_route(
    device_id: str,
    command: str,
    parameters: dict[str, Any] | None = None,
):
    device = get_enabled_device(device_id)

    try:
        return device_service.execute(device, command, parameters)
    except Exception as error:
        raise _handle_device_error(error) from error


@router.get("/api/devices/{device_id}/clients")
def get_device_clients(device_id: str):
    device = get_enabled_device(device_id)

    try:
        return {
            "device_id": device["id"],
            "clients": device_service.get_dhcp_clients(device),
        }
    except Exception as error:
        raise _handle_device_error(error) from error


@router.get("/api/integrations")
def get_integrations_list():
    return get_integrations()