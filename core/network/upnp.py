
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from core.network.ssdp import (
    SsdpDevice,
    discover_ssdp_devices,
)


MAX_DESCRIPTION_SIZE = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class UpnpService:
    service_type: str | None = None
    service_id: str | None = None
    scpd_url: str | None = None
    control_url: str | None = None
    event_sub_url: str | None = None


@dataclass(frozen=True, slots=True)
class UpnpDeviceInfo:
    friendly_name: str | None = None
    device_type: str | None = None

    manufacturer: str | None = None
    manufacturer_url: str | None = None

    model_description: str | None = None
    model_name: str | None = None
    model_number: str | None = None
    model_url: str | None = None

    serial_number: str | None = None
    udn: str | None = None

    parent_udn: str | None = None
    is_root: bool = False

    services: tuple[UpnpService, ...] = ()


@dataclass(frozen=True, slots=True)
class UpnpDeviceDescription:
    ip_address: str
    location: str

    server: str | None = None
    usn: str | None = None
    search_target: str | None = None

    devices: tuple[UpnpDeviceInfo, ...] = ()


@dataclass(frozen=True, slots=True)
class UpnpDiscoveryError:
    ip_address: str
    location: str
    message: str


@dataclass(frozen=True, slots=True)
class UpnpDiscoveryResult:
    devices: tuple[UpnpDeviceDescription, ...] = ()
    errors: tuple[UpnpDiscoveryError, ...] = ()


def _local_name(tag: str) -> str:
    """Remove an XML namespace from an element name."""

    return tag.rsplit("}", 1)[-1]


def _find_child(element, name: str):
    for child in element:
        if _local_name(child.tag) == name:
            return child

    return None


def _find_children(element, name: str):
    return [
        child
        for child in element
        if _local_name(child.tag) == name
    ]


def _get_text(element, name: str) -> str | None:
    child = _find_child(element, name)

    if child is None or child.text is None:
        return None

    value = child.text.strip()

    return value or None


def _download_description(
    location: str,
    timeout: float,
) -> bytes:
    parsed = urlsplit(location)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Unsupported description URL scheme")

    if not parsed.hostname:
        raise ValueError("Invalid description URL")

    request = urllib.request.Request(
        location,
        headers={
            "Accept": "application/xml, text/xml, */*",
        },
        method="GET",
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:
        data = response.read(MAX_DESCRIPTION_SIZE + 1)

    if len(data) > MAX_DESCRIPTION_SIZE:
        raise ValueError("UPnP description exceeds maximum size")

    if not data:
        raise ValueError("Empty UPnP description")

    return data


def _parse_services(
    device_element,
    base_url: str,
) -> tuple[UpnpService, ...]:
    service_list = _find_child(
        device_element,
        "serviceList",
    )

    if service_list is None:
        return ()

    services = []

    for element in _find_children(
        service_list,
        "service",
    ):
        scpd_url = _get_text(element, "SCPDURL")
        control_url = _get_text(element, "controlURL")
        event_sub_url = _get_text(element, "eventSubURL")

        services.append(
            UpnpService(
                service_type=_get_text(element, "serviceType"),
                service_id=_get_text(element, "serviceId"),
                scpd_url=(
                    urljoin(base_url, scpd_url)
                    if scpd_url
                    else None
                ),
                control_url=(
                    urljoin(base_url, control_url)
                    if control_url
                    else None
                ),
                event_sub_url=(
                    urljoin(base_url, event_sub_url)
                    if event_sub_url
                    else None
                ),
            )
        )

    return tuple(services)


def _parse_device_tree(
    device_element,
    base_url: str,
    parent_udn: str | None = None,
    is_root: bool = False,
) -> list[UpnpDeviceInfo]:
    udn = _get_text(device_element, "UDN")

    device = UpnpDeviceInfo(
        friendly_name=_get_text(
            device_element,
            "friendlyName",
        ),
        device_type=_get_text(
            device_element,
            "deviceType",
        ),
        manufacturer=_get_text(
            device_element,
            "manufacturer",
        ),
        manufacturer_url=_get_text(
            device_element,
            "manufacturerURL",
        ),
        model_description=_get_text(
            device_element,
            "modelDescription",
        ),
        model_name=_get_text(
            device_element,
            "modelName",
        ),
        model_number=_get_text(
            device_element,
            "modelNumber",
        ),
        model_url=_get_text(
            device_element,
            "modelURL",
        ),
        serial_number=_get_text(
            device_element,
            "serialNumber",
        ),
        udn=udn,
        parent_udn=parent_udn,
        is_root=is_root,
        services=_parse_services(
            device_element,
            base_url,
        ),
    )

    devices = [device]

    device_list = _find_child(
        device_element,
        "deviceList",
    )

    if device_list is None:
        return devices

    for child in _find_children(
        device_list,
        "device",
    ):
        devices.extend(
            _parse_device_tree(
                device_element=child,
                base_url=base_url,
                parent_udn=udn,
            )
        )

    return devices


def _parse_description(
    data: bytes,
    location: str,
    ip_address: str,
    server: str | None = None,
    usn: str | None = None,
    search_target: str | None = None,
) -> UpnpDeviceDescription:
    root = ET.fromstring(data)

    root_device = _find_child(
        root,
        "device",
    )

    if root_device is None:
        raise ValueError(
            "UPnP description does not contain a root device"
        )

    url_base = _get_text(root, "URLBase")
    base_url = urljoin(location, url_base) if url_base else location

    devices = _parse_device_tree(
        device_element=root_device,
        base_url=base_url,
        is_root=True,
    )

    return UpnpDeviceDescription(
        ip_address=ip_address,
        location=location,
        server=server,
        usn=usn,
        search_target=search_target,
        devices=tuple(devices),
    )


def get_upnp_device_description(
    location: str,
    timeout: float = 3.0,
) -> UpnpDeviceDescription:
    """Download and parse one UPnP device description."""

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    parsed = urlsplit(location)

    if not parsed.hostname:
        raise ValueError("Invalid description URL")

    data = _download_description(
        location=location,
        timeout=timeout,
    )

    return _parse_description(
        data=data,
        location=location,
        ip_address=parsed.hostname,
    )


def discover_upnp_devices(
    timeout: float = 5.0,
    description_timeout: float = 3.0,
    ssdp_results: tuple[SsdpDevice, ...] | None = None,
) -> UpnpDiscoveryResult:
    """
    Discover UPnP devices through SSDP and read their descriptions.

    Reuses supplied SSDP results to avoid scanning the network twice.
    Downloads each unique description URL only once.
    """

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    if description_timeout <= 0:
        raise ValueError(
            "description_timeout must be greater than zero"
        )

    ssdp_devices = (
        ssdp_results
        if ssdp_results is not None
        else discover_ssdp_devices(timeout=timeout)
    )

    descriptions = {}
    errors = []

    for ssdp_device in ssdp_devices:
        location = ssdp_device.location

        if not location:
            continue

        if location in descriptions:
            continue

        if any(
            error.location == location
            for error in errors
        ):
            continue

        try:
            data = _download_description(
                location=location,
                timeout=description_timeout,
            )

            description = _parse_description(
                data=data,
                location=location,
                ip_address=ssdp_device.ip_address,
                server=ssdp_device.server,
                usn=ssdp_device.usn,
                search_target=ssdp_device.search_target,
            )

            descriptions[location] = description

        except (
            OSError,
            urllib.error.URLError,
            ET.ParseError,
            ValueError,
        ) as error:
            errors.append(
                UpnpDiscoveryError(
                    ip_address=ssdp_device.ip_address,
                    location=location,
                    message=str(error),
                )
            )

    return UpnpDiscoveryResult(
        devices=tuple(descriptions.values()),
        errors=tuple(errors),
    )
