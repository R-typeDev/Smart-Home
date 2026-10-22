from fastapi import APIRouter
from fastapi.responses import FileResponse

from config import WEB_DIR

router = APIRouter()


@router.get("/")
@router.get("/dashboard")
@router.get("/devices")
@router.get("/network")
@router.get("/integrations")
@router.get("/settings")
def app_page():
    return FileResponse(WEB_DIR / "index.html")


@router.get("/devices/item/{device_id}")
@router.get("/devices/item/{device_id}/")
def device_detail_page(device_id: str):
    return FileResponse(WEB_DIR / "index.html")


@router.get("/network/item/{device_id}")
@router.get("/network/item/{device_id}/")
def network_device_detail_page(device_id: str):
    return FileResponse(WEB_DIR / "index.html")


@router.get("/pages/network/")
def network_page():
    return FileResponse(
        WEB_DIR / "pages" / "network" / "network.html"
    )


@router.get("/pages/network/item/{device_id}/")
def legacy_network_device_detail_page(device_id: str):
    return FileResponse(
        WEB_DIR / "pages" / "network" / "network-device.html"
    )


@router.get("/pages/devices/")
def devices_page():
    return FileResponse(
        WEB_DIR / "pages" / "devices" / "devices.html"
    )


@router.get("/pages/devices/item/{device_id}/")
def legacy_device_detail_page(device_id: str):
    return FileResponse(
        WEB_DIR / "pages" / "devices" / "device.html"
    )