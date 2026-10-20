
from fastapi import APIRouter
from fastapi.responses import FileResponse

from config import WEB_DIR

router = APIRouter()


@router.get("/")
def root():
    return FileResponse(WEB_DIR / "index.html")


@router.get("/pages/network/")
def network_page():
    return FileResponse(WEB_DIR / "pages" / "network.html")


@router.get("/pages/network/item/{device_id}/")
def network_device_detail_page(device_id: str):
    return FileResponse(WEB_DIR / "pages" / "network" / "detail.html")


@router.get("/pages/devices/")
def devices_page():
    return FileResponse(WEB_DIR / "pages" / "devices.html")


@router.get("/pages/devices/item/{device_id}/")
def device_detail_page(device_id: str):
    return FileResponse(WEB_DIR / "pages" / "devices" / "device.html")
