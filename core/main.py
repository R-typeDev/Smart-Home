
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from integrations.tplink_router.router import TPLinkRouterIntegration

load_dotenv()

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
    return {
        "name": "Smart Home",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


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
