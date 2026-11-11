
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from database.devices import (
    add_device,
    add_device_source,
    get_device,
    get_devices,
)
from database.integrations import (
    get_integrations,
    get_integration_instance,
    get_integration_settings,
    get_integration_secret,
)
from integrations.tuya.cloud.client import TuyaCloudClient
from services.device_service import device_service
from services.secret_service import decrypt_secret


router = APIRouter()


TUYA_CATEGORY_MAP = {
    "dj": {"category": "lighting", "type": "smart_bulb"},
    "cz": {"category": "power", "type": "smart_plug"},
    "mal": {"category": "security", "type": "alarm"},
}


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


def _get_registered_external_device(external_id: str):
    for device in get_devices():
        for source in device.get("sources", []):
            if source.get("external_id") == external_id:
                return device

    return None


def _get_tuya_cloud_client(instance_id: str):
    instance = get_integration_instance(instance_id)

    if instance is None or instance.get("integration_id") != "tuya_cloud":
        raise HTTPException(
            status_code=404,
            detail="Tuya Cloud connection not found.",
        )

    if not instance.get("enabled"):
        raise HTTPException(
            status_code=409,
            detail="Tuya Cloud connection is disabled.",
        )

    settings = get_integration_settings(instance_id)
    region = settings.get("region", {}).get("value")
    user_id = settings.get("user_id", {}).get("value")

    access_id = get_integration_secret(instance_id, "access_id")
    access_secret = get_integration_secret(instance_id, "access_secret")

    if not region or not user_id or not access_id or not access_secret:
        raise HTTPException(
            status_code=409,
            detail="Tuya Cloud connection is not configured.",
        )

    client = TuyaCloudClient(
        access_id=decrypt_secret(access_id),
        access_secret=decrypt_secret(access_secret),
        region=region,
    )

    return client, user_id


def _clean_tuya_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    # Avoid using visibly corrupted text as a device name or model.
    mojibake_markers = ("Ð", "Ñ", "Ã", "Â", "æ", "ä", "ç")
    if any(marker in value for marker in mojibake_markers):
        return None

    return value.strip()


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
            category=device.get("category"),
            device_type=device_type,
            manufacturer=device.get("manufacturer"),
            model=device.get("model"),
            barcode=device.get("barcode"),
            serial_number=device.get("serial_number"),
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


@router.post("/api/devices/discovery/register")
def register_discovered_device(payload: dict[str, Any]):
    integration_id = payload.get("integration_id")
    instance_id = payload.get("instance_id")
    external_id = payload.get("external_id")

    if integration_id != "tuya_cloud":
        raise HTTPException(
            status_code=422,
            detail="Unsupported discovery integration.",
        )

    if not isinstance(instance_id, str) or not instance_id.strip():
        raise HTTPException(
            status_code=422,
            detail="Cloud connection ID is required.",
        )

    if not isinstance(external_id, str) or not external_id.strip():
        raise HTTPException(
            status_code=422,
            detail="External device ID is required.",
        )

    try:
        client, user_id = _get_tuya_cloud_client(instance_id)

        response = client.get_user_devices(user_id=user_id)
        cloud_devices = response.get("result") or []

        if not isinstance(cloud_devices, list):
            raise HTTPException(
                status_code=502,
                detail="Unexpected Tuya Cloud devices response.",
            )

        cloud_device = next(
            (
                item
                for item in cloud_devices
                if isinstance(item, dict)
                and item.get("id") == external_id
            ),
            None,
        )

        if cloud_device is None:
            raise HTTPException(
                status_code=404,
                detail="Device was not found in this Tuya Cloud account.",
            )

        # If the physical device is already registered, attach Cloud
        # as another source instead of creating a duplicate.
        existing_device = _get_registered_external_device(external_id)

        if existing_device is not None:
            add_device_source(
                device_id=existing_device["id"],
                instance_id=instance_id,
                external_id=external_id,
                source_name="Tuya Cloud",
                enabled=True,
                priority=100,
            )

            return {
                "success": True,
                "already_registered": True,
                "device": get_device(existing_device["id"]),
            }

        category_info = TUYA_CATEGORY_MAP.get(
            cloud_device.get("category"),
            {},
        )

        product_name = _clean_tuya_text(
            cloud_device.get("product_name")
        )
        cloud_name = _clean_tuya_text(cloud_device.get("name"))
        model = _clean_tuya_text(cloud_device.get("model"))

        name = (
            payload.get("name")
            or cloud_name
            or product_name
            or "Tuya device"
        )

        if not isinstance(name, str) or not name.strip():
            raise HTTPException(
                status_code=422,
                detail="A valid device name is required.",
            )

        device_id = str(uuid.uuid4())

        created = add_device(
            device_id=device_id,
            name=name.strip(),
            category=category_info.get("category"),
            device_type=category_info.get("type", "unknown"),
            manufacturer=_clean_tuya_text(
                cloud_device.get("brand")
                or cloud_device.get("manufacturer")
            ),
            model=model,
            enabled=True,
        )

        add_device_source(
            device_id=created["id"],
            instance_id=instance_id,
            external_id=external_id,
            source_name="Tuya Cloud",
            enabled=True,
            priority=100,
        )

        return {
            "success": True,
            "already_registered": False,
            "device": get_device(created["id"]),
        }

    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not register discovered device: {type(error).__name__}",
        ) from error


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
