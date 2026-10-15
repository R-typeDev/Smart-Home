
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
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


@app.get("/")
def root():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/pages/network/")
def network_page():
    return FileResponse(WEB_DIR / "pages" / "network" / "index.html")


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


def get_tuya_plug_integration() -> TuyaPlugIntegration:
    try:
        return TuyaPlugIntegration()
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.get("/api/devices/plug")
def get_tuya_plug_status():
    integration = get_tuya_plug_integration()

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
        "name": "Smart Plug",
        "power": dps.get("1"),
    }
