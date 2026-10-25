import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from core.database.devices import add_device, get_device, get_devices
from core.database.integrations import get_integrations
from services.device_service import device_service
from services.integration_registry import integration_registry

router = APIRouter()


def get_enabled_device(device_id: str) -> dict[str, Any]:
    device = get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    if device["enabled"] != 1:
        raise HTTPException(status_code=409, detail="Device is disabled.")

    if not device.get("integration_id"):
        raise HTTPException(
            status_code=409,
            detail="Device has no assigned integration.",
        )

    return device


def get_device_capabilities(device: dict[str, Any]) -> set[str]:
    try:
        return device_service.get_capabilities(device)
    except LookupError as error:
        raise HTTPException(
            status_code=503,
            detail="Device integration is not available.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not retrieve device capabilities: "
                f"{type(error).__name__}"
            ),
        ) from error


def get_device_commands(
    device: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    try:
        return device_service.get_commands(device)
    except LookupError as error:
        raise HTTPException(
            status_code=503,
            detail="Device integration is not available.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve device commands: {type(error).__name__}",
        ) from error


def get_device_state(device: dict[str, Any]) -> dict[str, Any]:
    try:
        return device_service.get_state(device)
    except LookupError as error:
        raise HTTPException(
            status_code=503,
            detail="Device integration is not available.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve device state: {type(error).__name__}",
        ) from error


def execute_device_command(
    device: dict[str, Any],
    command: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        return device_service.execute(device, command, parameters)
    except LookupError as error:
        raise HTTPException(
            status_code=503,
            detail="Device integration is not available.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not execute device command: {type(error).__name__}",
        ) from error


@router.get("/api/devices")
def get_devices_list():
    return get_devices()


@router.post("/api/devices")
def create_device(device: dict[str, Any]):
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


@router.get("/api/devices/{device_id}/capabilities")
def get_device_capabilities_route(device_id: str):
    device = get_enabled_device(device_id)

    return {
        "device_id": device["id"],
        "capabilities": sorted(get_device_capabilities(device)),
    }


@router.get("/api/devices/{device_id}/commands")
def get_device_commands_route(device_id: str):
    device = get_enabled_device(device_id)

    return {
        "device_id": device["id"],
        "commands": get_device_commands(device),
    }


@router.get("/api/devices/{device_id}/state")
def get_device_state_route(device_id: str):
    device = get_enabled_device(device_id)

    return {
        "device_id": device["id"],
        "name": device["name"],
        **get_device_state(device),
    }


@router.post("/api/devices/{device_id}/commands/{command}")
def execute_device_command_route(
    device_id: str,
    command: str,
    parameters: dict[str, Any] | None = None,
):
    device = get_enabled_device(device_id)

    return execute_device_command(device, command, parameters)


@router.get("/api/devices/{device_id}/clients")
def get_device_clients(device_id: str):
    device = get_enabled_device(device_id)

    try:
        integration = integration_registry.get(device["integration_id"])
    except LookupError as error:
        raise HTTPException(
            status_code=503,
            detail="Device integration is not available.",
        ) from error

    get_clients = getattr(integration, "get_dhcp_clients", None)

    if not callable(get_clients):
        raise HTTPException(
            status_code=409,
            detail="This device does not support retrieving connected clients.",
        )

    try:
        return {
            "device_id": device["id"],
            "clients": get_clients(device),
        }
    except LookupError as error:
        raise HTTPException(
            status_code=503,
            detail="Device integration is not available.",
        ) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Could not retrieve connected clients: "
                f"{type(error).__name__}"
            ),
        ) from error


@router.get("/api/integrations")
def get_integrations_list():
    return get_integrations()


@router.get("/api/devices/{device_id}")
def get_device_by_id(device_id: str):
    device = get_device(device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found.")

    return device