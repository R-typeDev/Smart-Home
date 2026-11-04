
from typing import Any

from fastapi import APIRouter, HTTPException

from database.integrations import get_integration
from integrations.catalog import PLATFORM_CATALOG
from services.integration_manager import integration_manager
from services.integration_registry import integration_registry


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


@router.get("/api/integrations/catalog")
def get_integrations_catalog():
    result = []

    for platform in PLATFORM_CATALOG:
        methods = [
            _method_catalog(method)
            for method in platform["methods"]
        ]

        statuses = [method["status"] for method in methods]

        if "enabled" in statuses:
            platform_status = "enabled"
        elif "error" in statuses:
            platform_status = "error"
        elif any(method["implemented"] for method in methods):
            platform_status = "disabled"
        else:
            platform_status = "not_implemented"

        result.append({
            **platform,
            "status": platform_status,
            "methods": methods,
        })

    return result


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
