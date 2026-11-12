
from typing import Any

from fastapi import APIRouter, HTTPException

from database.devices import get_device, get_devices
from database.integrations import (
    add_integration_instance,
    get_integration,
    get_integration_instance,
    get_integration_instances,
    get_integration_settings,
    set_integration_setting,
    set_integration_secret,
)
from integrations.catalog import PLATFORM_CATALOG
from services.integration_manager import integration_manager
from services.integration_registry import integration_registry
from services.secret_service import encrypt_secret


router = APIRouter()


def _get_adapter(integration_id: str):
    if not integration_registry.is_registered(integration_id):
        raise HTTPException(
            status_code=404,
            detail="Integration adapter is not registered.",
        )

    adapter = integration_registry.get(integration_id)

    if adapter is None:
        raise HTTPException(
            status_code=404,
            detail="Integration adapter was not found.",
        )

    return adapter


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


def _get_instance_or_404(
    integration_id: str,
    instance_id: str,
) -> dict[str, Any]:
    instance = get_integration_instance(instance_id)

    if instance is None or instance["integration_id"] != integration_id:
        raise HTTPException(
            status_code=404,
            detail="Integration connection not found.",
        )

    return instance


def _safe_settings(instance_id: str) -> dict[str, Any]:
    return get_integration_settings(instance_id)


def _normalize_device(
    adapter: Any,
    raw_device: dict[str, Any],
    instance_id: str | None = None,
) -> dict[str, Any]:
    normalizer = getattr(adapter, "normalize_device", None)

    if not callable(normalizer):
        raise HTTPException(
            status_code=501,
            detail="This integration does not support device normalization.",
        )

    normalized = normalizer(raw_device, instance_id)

    if not isinstance(normalized, dict):
        raise HTTPException(
            status_code=502,
            detail="Integration returned an invalid device.",
        )

    return normalized


def _get_registered_devices(
    integration_id: str,
) -> dict[str, dict[str, Any]]:
    registered = {}

    for item in get_devices():
        device = get_device(item["id"])

        if device is None:
            continue

        properties = device.get("properties", {})

        for source in device.get("sources", []):
            if source.get("integration_id") != integration_id:
                continue

            external_id = source.get("external_id")

            if not external_id:
                continue

            registered[str(external_id)] = {
                "id": device["id"],
                "name": device.get("name"),
                "category": device.get("category"),
                "type": device.get("type"),
                "properties": properties,
                "source": {
                    "integration_id": integration_id,
                    "source_name": source.get("source_name"),
                    "instance_id": source.get("instance_id"),
                    "external_id": external_id,
                    "enabled": bool(source.get("enabled")),
                    "connection_enabled": bool(
                        source.get("connection_enabled")
                    ),
                    "integration_enabled": bool(
                        source.get("integration_enabled")
                    ),
                },
            }

    return registered


def _get_local_connection_device(
    instance_id: str,
) -> dict[str, Any]:
    for item in get_devices():
        device = get_device(item["id"])

        if device is None:
            continue

        for source in device.get("sources", []):
            if (
                source.get("integration_id") == "tuya_local"
                and source.get("instance_id") == instance_id
            ):
                if not source.get("enabled"):
                    raise HTTPException(
                        status_code=409,
                        detail="Device source is disabled.",
                    )

                return {
                    **device,
                    "instance_id": instance_id,
                    "external_id": source.get("external_id"),
                }

    raise HTTPException(
        status_code=404,
        detail="No registered Tuya Local device uses this connection.",
    )


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


@router.get(
    "/api/integrations/{integration_id}/connection-setup-schema"
)
def get_connection_setup_schema(
    integration_id: str,
    device_type: str | None = None,
):
    try:
        return integration_registry.get_connection_setup_schema(
            integration_id,
            context={"device_type": device_type},
        )
    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not retrieve connection setup schema: "
                f"{type(error).__name__}"
            ),
        ) from error


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
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not change integration state: {type(error).__name__}",
        ) from error


# ---------------------------------------------------------
# Generic connection management
# ---------------------------------------------------------

@router.get("/api/integrations/{integration_id}/connections")
def get_integration_connections(integration_id: str):
    if get_integration(integration_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Integration not found.",
        )

    connections = get_integration_instances(integration_id)

    adapter = (
        integration_registry.get(integration_id)
        if integration_registry.is_registered(integration_id)
        else None
    )

    configuration_checker = getattr(
        adapter,
        "is_configured",
        None,
    )

    result = []

    for item in connections:
        configured = (
            bool(configuration_checker(item["id"]))
            if callable(configuration_checker)
            else None
        )

        result.append({
            "id": item["id"],
            "name": item["name"],
            "enabled": bool(item["enabled"]),
            "integration_id": item["integration_id"],
            "configured": configured,
            "settings": _safe_settings(item["id"]),
        })

    return result


@router.post("/api/integrations/{integration_id}/connections")
def create_integration_connection(
    integration_id: str,
    payload: dict[str, Any],
):
    if get_integration(integration_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Integration not found.",
        )

    name = payload.get("name")
    settings = payload.get("settings", {})
    secrets = payload.get("secrets", {})

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(
            status_code=422,
            detail="Connection name is required.",
        )

    if not isinstance(settings, dict) or not isinstance(secrets, dict):
        raise HTTPException(
            status_code=422,
            detail="Settings and secrets must be objects.",
        )

    try:
        connection = add_integration_instance(
            integration_id=integration_id,
            name=name.strip(),
        )

        instance_id = connection["id"]

        for key, value in settings.items():
            if isinstance(key, str) and key:
                set_integration_setting(instance_id, key, value)

        for key, value in secrets.items():
            if (
                isinstance(key, str)
                and key
                and isinstance(value, str)
                and value
            ):
                set_integration_secret(
                    instance_id,
                    key,
                    encrypt_secret(value),
                )

        return {
            "id": instance_id,
            "name": connection["name"],
            "integration_id": integration_id,
            "enabled": bool(connection["enabled"]),
            "configured": True,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not create integration connection: "
                f"{type(error).__name__}"
            ),
        ) from error


@router.put(
    "/api/integrations/{integration_id}/connections/{instance_id}"
)
def update_integration_connection(
    integration_id: str,
    instance_id: str,
    payload: dict[str, Any],
):
    instance = _get_instance_or_404(integration_id, instance_id)

    settings = payload.get("settings", {})
    secrets = payload.get("secrets", {})

    if not isinstance(settings, dict) or not isinstance(secrets, dict):
        raise HTTPException(
            status_code=422,
            detail="Settings and secrets must be objects.",
        )

    try:
        for key, value in settings.items():
            if isinstance(key, str) and key:
                set_integration_setting(instance_id, key, value)

        for key, value in secrets.items():
            if (
                isinstance(key, str)
                and key
                and isinstance(value, str)
                and value
            ):
                set_integration_secret(
                    instance_id,
                    key,
                    encrypt_secret(value),
                )

        return {
            "id": instance_id,
            "name": instance["name"],
            "integration_id": integration_id,
            "updated": True,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not update integration connection: "
                f"{type(error).__name__}"
            ),
        ) from error


@router.post(
    "/api/integrations/{integration_id}/connections/{instance_id}/test"
)
def test_integration_connection(
    integration_id: str,
    instance_id: str,
    payload: dict[str, Any] | None = None,
):
    _get_instance_or_404(integration_id, instance_id)
    adapter = _get_adapter(integration_id)

    tester = getattr(adapter, "test_connection", None)

    if not callable(tester):
        raise HTTPException(
            status_code=501,
            detail="This integration does not support connection testing.",
        )

    try:
        if integration_id == "tuya_local":
            test_target = _get_local_connection_device(instance_id)
        else:
            test_target = instance_id

        result = tester(test_target)

        if not isinstance(result, dict):
            raise RuntimeError("Integration returned an invalid test result.")

        return result

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Connection test failed: {type(error).__name__}",
        ) from error


# ---------------------------------------------------------
# Generic device discovery
# ---------------------------------------------------------

@router.get("/api/integrations/{integration_id}/devices")
def get_integration_devices(
    integration_id: str,
    instance_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=422,
            detail="Invalid pagination parameters.",
        )

    if get_integration(integration_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Integration not found.",
        )

    adapter = _get_adapter(integration_id)
    discover = getattr(adapter, "discover_devices", None)

    if callable(discover):
        try:
            raw_devices = discover(
                instance_id=instance_id,
                page=page,
                page_size=page_size,
            )
        except Exception as error:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Device discovery failed: "
                    f"{type(error).__name__}: {error}"
                ),
            ) from error

        if not isinstance(raw_devices, list):
            raise HTTPException(
                status_code=502,
                detail="Integration returned an invalid device list.",
            )

        registered = _get_registered_devices(integration_id)
        devices = []

        for raw_device in raw_devices:
            if not isinstance(raw_device, dict):
                continue

            normalized = _normalize_device(
                adapter,
                raw_device,
                instance_id,
            )

            external_id = str(normalized.get("external_id", ""))
            registered_device = registered.get(external_id)

            devices.append({
                **normalized,
                "is_registered": registered_device is not None,
                "registered_device": registered_device,
            })

        return {
            "integration_id": integration_id,
            "instance_id": instance_id,
            "page": page,
            "page_size": page_size,
            "devices_total": len(devices),
            "devices": devices,
        }

    registered_devices = []

    for item in get_devices():
        device = get_device(item["id"])

        if device is None:
            continue

        properties = device.get("properties", {})

        for source in device.get("sources", []):
            if source.get("integration_id") != integration_id:
                continue

            if instance_id and source.get("instance_id") != instance_id:
                continue

            ip_address = properties.get("ip_address", {})
            tuya_version = properties.get("tuya_version", {})

            registered_devices.append({
                "id": device["id"],
                "name": device.get("name"),
                "type": device.get("type"),
                "category": device.get("category"),
                "source_name": source.get("source_name"),
                "instance_id": source.get("instance_id"),
                "external_id": source.get("external_id"),
                "ip_address": (
                    ip_address.get("value")
                    if isinstance(ip_address, dict)
                    else ip_address
                ),
                "version": (
                    tuya_version.get("value", "3.5")
                    if isinstance(tuya_version, dict)
                    else tuya_version or "3.5"
                ),
                "properties": properties,
                "enabled": bool(source.get("enabled")),
                "connection_enabled": bool(
                    source.get("connection_enabled")
                ),
                "integration_enabled": bool(
                    source.get("integration_enabled")
                ),
            })

    return {
        "integration_id": integration_id,
        "instance_id": instance_id,
        "page": page,
        "page_size": page_size,
        "devices_total": len(registered_devices),
        "devices": registered_devices,
    }


@router.post(
    "/api/integrations/{integration_id}/devices/{device_id}/test"
)
def test_integration_device(
    integration_id: str,
    device_id: str,
):
    device = get_device(device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not found.",
        )

    adapter = _get_adapter(integration_id)
    tester = getattr(adapter, "test_connection", None)

    if not callable(tester):
        raise HTTPException(
            status_code=501,
            detail="This integration does not support device testing.",
        )

    source = next(
        (
            item
            for item in device.get("sources", [])
            if item.get("integration_id") == integration_id
        ),
        None,
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail="Device source not found.",
        )

    if not source.get("enabled"):
        raise HTTPException(
            status_code=409,
            detail="Device source is disabled.",
        )

    try:
        result = tester({
            **device,
            "instance_id": source.get("instance_id"),
            "external_id": source.get("external_id"),
        })

        if not isinstance(result, dict):
            raise RuntimeError("Integration returned an invalid test result.")

        return result

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Device test failed: {type(error).__name__}",
        ) from error
