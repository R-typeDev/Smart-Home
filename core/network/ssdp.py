
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from core.network.interfaces.detector import get_network_interfaces
from core.network.interfaces.models import (
    AddressType,
    InterfaceType,
    NetworkInterface,
)


SSDP_ADDRESS = "239.255.255.250"
SSDP_PORT = 1900


@dataclass(frozen=True, slots=True)
class SsdpDevice:
    ip_address: str
    location: str | None = None
    server: str | None = None
    usn: str | None = None
    search_target: str | None = None
    cache_control: str | None = None
    headers: tuple[tuple[str, str], ...] = ()


def _get_local_ipv4_addresses(
    interfaces: list[NetworkInterface] | tuple[NetworkInterface, ...] | None = None,
) -> tuple[str, ...]:
    """Get usable IPv4 addresses from active physical interfaces."""

    if interfaces is None:
        interfaces = get_network_interfaces()

    addresses = []

    for interface in interfaces:
        if not interface.is_up:
            continue

        if interface.is_loopback or interface.is_virtual:
            continue

        if interface.interface_type not in (
            InterfaceType.ETHERNET,
            InterfaceType.WIFI,
        ):
            continue

        for address in interface.addresses:
            if address.address_type != AddressType.IPV4:
                continue

            if address.is_link_local:
                continue

            if address.address not in addresses:
                addresses.append(address.address)

    return tuple(addresses)


def _build_search_request() -> bytes:
    request = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDRESS}:{SSDP_PORT}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        "ST: ssdp:all\r\n"
        "\r\n"
    )

    return request.encode("ascii")


def _parse_response(
    data: bytes,
    source_ip: str,
) -> SsdpDevice | None:
    lines = data.decode(
        "utf-8",
        errors="replace",
    ).splitlines()

    if not lines or not lines[0].startswith("HTTP/1.1 200"):
        return None

    headers = {}

    for line in lines[1:]:
        if ":" not in line:
            continue

        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    if not headers:
        return None

    return SsdpDevice(
        ip_address=source_ip,
        location=headers.get("location"),
        server=headers.get("server"),
        usn=headers.get("usn"),
        search_target=headers.get("st"),
        cache_control=headers.get("cache-control"),
        headers=tuple(sorted(headers.items())),
    )


def _discover_on_interface(
    local_ip: str,
    timeout: float,
) -> tuple[SsdpDevice, ...]:
    devices = {}

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
        socket.IPPROTO_UDP,
    ) as client:
        client.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        client.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_MULTICAST_TTL,
            2,
        )

        client.setsockopt(
            socket.IPPROTO_IP,
            socket.IP_MULTICAST_IF,
            socket.inet_aton(local_ip),
        )

        client.bind((local_ip, 0))
        client.settimeout(0.25)

        client.sendto(
            _build_search_request(),
            (SSDP_ADDRESS, SSDP_PORT),
        )

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                response, address = client.recvfrom(65535)
            except socket.timeout:
                continue

            device = _parse_response(
                response,
                address[0],
            )

            if device is None:
                continue

            key = (
                device.ip_address,
                device.usn,
                device.search_target,
            )

            devices[key] = device

    return tuple(devices.values())


def discover_ssdp_devices(
    timeout: float = 5.0,
    interfaces: list[NetworkInterface] | tuple[NetworkInterface, ...] | None = None,
) -> tuple[SsdpDevice, ...]:
    """Discover UPnP devices through active physical interfaces."""

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    local_addresses = _get_local_ipv4_addresses(interfaces)

    if not local_addresses:
        return ()

    devices = {}

    with ThreadPoolExecutor(max_workers=len(local_addresses)) as executor:
        futures = {
            executor.submit(
                _discover_on_interface,
                local_ip,
                timeout,
            ): local_ip
            for local_ip in local_addresses
        }

        for future in as_completed(futures):
            try:
                results = future.result()
            except OSError:
                continue

            for device in results:
                key = (
                    device.ip_address,
                    device.usn,
                    device.search_target,
                )

                devices[key] = device

    return tuple(
        sorted(
            devices.values(),
            key=lambda device: (
                device.ip_address,
                device.search_target or "",
                device.usn or "",
            ),
        )
    )
