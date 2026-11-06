from typing import Any

from fastapi import APIRouter, HTTPException

from database.devices import (
    get_device,
    get_devices,
    get_device_source_secret,
)
from database.integrations import (
    add_integration_instance,
    get_integration,
    get_integration_instance,
    get_integration_instances,
    get_integration_settings,
    get_integration_secret,
    set_integration_setting,
    set_integration_secret,
)
from integrations.catalog import PLATFORM_CATALOG
from integrations.tuya.cloud.client import (
    TUYA_REGIONS,
    TuyaCloudClient,
)
from integrations.tuya.local.devices.plug import TuyaPlugIntegration
from services.integration_manager import integration_manager
from services.integration_registry import integration_registry
from services.secret_service import encrypt_secret, decrypt_secret


router = APIRouter()


def _method_catalog(method: dict[str, Any]) -> dict[str, Any]:
    integration_id = method["id"]
    database_record = get_integration(integration_id)
    implemented = integration_registry.is_registered(integration_id)

    enabled = (
        bool(database_record["enabled"])
        if implemented and database_record is not None
        else None
    )

    active = (
        integration_registry.is_enabled(integration_id)
        if implemented
        else False
    )

    if not implemented:
        status = "not_implemented"
    elif enabled and active:
        status = "enabled"
    elif enabled and not active:
        status = "error"
    else:
        status = "disabled"

    return {
        **method,
        "implemented": implemented,
        "enabled": enabled,
        "active": active,
        "status": status,
    }


def _get_tuya_cloud_client(instance_id: str) -> TuyaCloudClient:
    instance = get_integration_instance(instance_id)

    if instance is None or instance["integration_id"] != "tuya_cloud":
        raise HTTPException(
            status_code=404,
            detail="Tuya Cloud connection not found.",
        )

    settings = get_integration_settings(instance_id)

    region = settings.get("region", {}).get("value")

    access_id = get_integration_secret(instance_id, "access_id")
    access_secret = get_integration_secret(instance_id, "access_secret")

    if not region or not access_id or not access_secret:
        raise HTTPException(
            status_code=409,
            detail="Tuya Cloud connection is not configured.",
        )

    return TuyaCloudClient(
        access_id=decrypt_secret(access_id),
        access_secret=decrypt_secret(access_secret),
        region=region,
    )


def _get_tuya_local_client(device_id: str):
    device = get_device(device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found.",
        )

    if device.get("type") != "smart_plug":
        raise HTTPException(
            status_code=409,
            detail="This Tuya Local device type is not supported yet.",
        )

    sources = device.get("sources", [])

    source = next(
        (
            item
            for item in sources
            if item.get("integration_id") == "tuya_local"
        ),
        None,
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail="Tuya Local source not found for this device.",
        )

    if not source.get("enabled"):
        raise HTTPException(
            status_code=409,
            detail="Tuya Local device source is disabled.",
        )

    if not source.get("connection_enabled"):
        raise HTTPException(
            status_code=409,
            detail="Tuya Local connection is disabled.",
        )

    if not source.get("integration_enabled"):
        raise HTTPException(
            status_code=409,
            detail="Tuya Local integration is disabled.",
        )

    properties = device.get("properties", {})

    ip_address = properties.get("ip_address", {}).get("value")
    version = properties.get("tuya_version", {}).get("value", "3.5")

    if not ip_address:
        raise HTTPException(
            status_code=409,
            detail="Local IP address is not configured.",
        )

    encrypted_key = get_device_source_secret(
        device_id,
        source["instance_id"],
        "local_key",
    )

    if not encrypted_key:
        raise HTTPException(
            status_code=409,
            detail="Tuya Local Key is not configured.",
        )

    local_key = decrypt_secret(encrypted_key)

    client = TuyaPlugIntegration(
        device_id=source["external_id"],
        ip_address=ip_address,
        local_key=local_key,
        version=version,
    )

    return device, source, client


@router.get("/api/integrations/catalog")
def get_integrations_catalog():
    return [
        {
            **platform,
            "methods": [
                _method_catalog(method)
                for method in platform["methods"]
            ],
        }
        for platform in PLATFORM_CATALOG
    ]


@router.get("/api/integrations/{integration_id}/status")
def get_integration_status(integration_id: str):
    database_record = get_integration(integration_id)

    if database_record is None:
        raise HTTPException(
            status_code=404,
            detail="Integration not found.",
        )

    implemented = integration_registry.is_registered(integration_id)

    return {
        "id": integration_id,
        "implemented": implemented,
        "enabled": (
            bool(database_record["enabled"])
            if implemented
            else None
        ),
        "active": integration_registry.is_enabled(integration_id),
    }


@router.put("/api/integrations/{integration_id}/enabled")
def update_integration_enabled(
    integration_id: str,
    payload: dict[str, Any],
):
    enabled = payload.get("enabled")

    if not isinstance(enabled, bool):
        raise HTTPException(
            status_code=422,
            detail="'enabled' must be a boolean.",
        )

    try:
        return integration_manager.set_enabled(
            integration_id,
            enabled,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not change integration state: {type(error).__name__}",
        ) from error


# ---------------------------------------------------------
# Tuya Cloud
# ---------------------------------------------------------

@router.get("/api/integrations/tuya_cloud/connections")
def get_tuya_cloud_connections():
    connections = get_integration_instances("tuya_cloud")

    return [
        {
            "id": item["id"],
            "name": item["name"],
            "enabled": bool(item["enabled"]),
            "integration_id": item["integration_id"],
            "settings": get_integration_settings(item["id"]),
            "configured": bool(
                get_integration_secret(item["id"], "access_id")
                and get_integration_secret(item["id"], "access_secret")
            ),
        }
        for item in connections
    ]


@router.post("/api/integrations/tuya_cloud/connections")
def create_tuya_cloud_connection(payload: dict[str, Any]):
    name = payload.get("name")
    region = payload.get("region")
    user_id = payload.get("user_id")
    access_id = payload.get("access_id")
    access_secret = payload.get("access_secret")

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(
            status_code=422,
            detail="Connection name is required.",
        )

    if region not in TUYA_REGIONS:
        raise HTTPException(
            status_code=422,
            detail="Unsupported Tuya Cloud region.",
        )

    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=422,
            detail="Tuya User ID is required.",
        )

    if not isinstance(access_id, str) or not access_id.strip():
        raise HTTPException(
            status_code=422,
            detail="Tuya Access ID is required.",
        )

    if not isinstance(access_secret, str) or not access_secret.strip():
        raise HTTPException(
            status_code=422,
            detail="Tuya Access Secret is required.",
        )

    if get_integration("tuya_cloud") is None:
        raise HTTPException(
            status_code=404,
            detail="Tuya Cloud integration is not registered in the database.",
        )

    try:
        connection = add_integration_instance(
            integration_id="tuya_cloud",
            name=name,
        )

        instance_id = connection["id"]

        set_integration_setting(instance_id, "region", region)
        set_integration_setting(instance_id, "user_id", user_id.strip())

        set_integration_secret(
            instance_id,
            "access_id",
            encrypt_secret(access_id.strip()),
        )

        set_integration_secret(
            instance_id,
            "access_secret",
            encrypt_secret(access_secret.strip()),
        )

        return {
            "id": instance_id,
            "name": connection["name"],
            "integration_id": "tuya_cloud",
            "enabled": bool(connection["enabled"]),
            "configured": True,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not create Tuya Cloud connection: {type(error).__name__}",
        ) from error


@router.put("/api/integrations/tuya_cloud/connections/{instance_id}")
def update_tuya_cloud_connection(
    instance_id: str,
    payload: dict[str, Any],
):
    instance = get_integration_instance(instance_id)

    if instance is None or instance["integration_id"] != "tuya_cloud":
        raise HTTPException(
            status_code=404,
            detail="Tuya Cloud connection not found.",
        )

    region = payload.get("region")
    user_id = payload.get("user_id")
    access_id = payload.get("access_id")
    access_secret = payload.get("access_secret")

    if region is not None:
        if region not in TUYA_REGIONS:
            raise HTTPException(
                status_code=422,
                detail="Unsupported Tuya Cloud region.",
            )

        set_integration_setting(instance_id, "region", region)

    if user_id is not None:
        if not isinstance(user_id, str) or not user_id.strip():
            raise HTTPException(
                status_code=422,
                detail="Tuya User ID cannot be empty.",
            )

        set_integration_setting(instance_id, "user_id", user_id.strip())

    if access_id is not None:
        if not isinstance(access_id, str) or not access_id.strip():
            raise HTTPException(
                status_code=422,
                detail="Tuya Access ID cannot be empty.",
            )

        set_integration_secret(
            instance_id,
            "access_id",
            encrypt_secret(access_id.strip()),
        )

    if access_secret is not None:
        if not isinstance(access_secret, str) or not access_secret.strip():
            raise HTTPException(
                status_code=422,
                detail="Tuya Access Secret cannot be empty.",
            )

        set_integration_secret(
            instance_id,
            "access_secret",
            encrypt_secret(access_secret.strip()),
        )

    return {
        "id": instance_id,
        "name": instance["name"],
        "updated": True,
    }


@router.post("/api/integrations/tuya_cloud/connections/{instance_id}/test")
def test_tuya_cloud_connection(instance_id: str):
    try:
        client = _get_tuya_cloud_client(instance_id)

        settings = get_integration_settings(instance_id)
        user_id = settings.get("user_id", {}).get("value")

        if not user_id:
            raise HTTPException(
                status_code=409,
                detail="Tuya User ID is not configured.",
            )

        response = client.get_user_devices(user_id=user_id)
        devices = response.get("result") or []

        if not isinstance(devices, list):
            raise HTTPException(
                status_code=502,
                detail="Unexpected Tuya Cloud devices response.",
            )

        return {
            "connected": True,
            "integration_id": "tuya_cloud",
            "devices_total": len(devices),
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Tuya Cloud connection failed: {type(error).__name__}",
        ) from error


@router.get("/api/integrations/tuya_cloud/connections/{instance_id}/devices")
def get_tuya_cloud_devices(instance_id: str):
    try:
        client = _get_tuya_cloud_client(instance_id)

        settings = get_integration_settings(instance_id)
        user_id = settings.get("user_id", {}).get("value")

        if not user_id:
            raise HTTPException(
                status_code=409,
                detail="Tuya User ID is not configured.",
            )

        return client.get_user_devices(user_id=user_id)

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Could not retrieve Tuya devices: {type(error).__name__}",
        ) from error


# ---------------------------------------------------------
# Tuya Local
# ---------------------------------------------------------

@router.get("/api/integrations/tuya_local/devices")
def get_tuya_local_devices():
    result = []

    for item in get_devices():
        device_id = item["id"]
        device = get_device(device_id)

        if device is None:
            continue

        for source in device.get("sources", []):
            if source.get("integration_id") != "tuya_local":
                continue

            properties = device.get("properties", {})
            ip_address = properties.get("ip_address", {}).get("value")
            version = properties.get("tuya_version", {}).get("value", "3.5")

            result.append({
                "id": device["id"],
                "name": device.get("name") or "Tuya device",
                "type": device.get("type"),
                "source_name": source.get("source_name") or "Tuya Local",
                "connection_name": source.get("connection_name") or "Tuya",
                "ip_address": ip_address,
                "version": version,
                "enabled": bool(source.get("enabled")),
                "connection_enabled": bool(source.get("connection_enabled")),
                "integration_enabled": bool(source.get("integration_enabled")),
            })

    return result


@router.post("/api/integrations/tuya_local/devices/{device_id}/test")
def test_tuya_local_device(device_id: str):
    try:
        device, source, client = _get_tuya_local_client(device_id)
        response = client.get_status()

        if not isinstance(response, dict):
            raise RuntimeError("Unexpected Tuya Local response.")

        dps = response.get("dps", {})
        power = dps.get("1")

        return {
            "connected": True,
            "device_id": device_id,
            "name": device.get("name"),
            "ip_address": device.get("properties", {})
                .get("ip_address", {})
                .get("value"),
            "version": device.get("properties", {})
                .get("tuya_version", {})
                .get("value", "3.5"),
            "power": power,
            "online": True,
            "dps": dps,
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Tuya Local connection failed: {type(error).__name__}",
        ) from error