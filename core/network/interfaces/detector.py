
import json
import platform
import socket
import subprocess
from ipaddress import ip_address, ip_interface

import psutil

from core.network.interfaces.classifier import classify_interface
from core.network.interfaces.models import (
    AddressType,
    InterfaceAddress,
    InterfaceType,
    NetworkInterface,
)


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _get_interface_index(name: str) -> int | None:
    try:
        return socket.if_nametoindex(name)
    except (OSError, ValueError):
        return None


def _get_windows_network_data() -> tuple[list[dict], list[dict]]:
    if platform.system() != "Windows":
        return [], []

    script = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$adapters = @(
    Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue |
    Select-Object Name, InterfaceDescription, ifIndex,
        Status, MacAddress, LinkSpeed, MediaType, Virtual
)

$addresses = @(
    Get-NetIPAddress -ErrorAction SilentlyContinue |
    Select-Object InterfaceAlias, InterfaceIndex,
        AddressFamily, IPAddress, PrefixLength
)

[PSCustomObject]@{
    adapters = $adapters
    addresses = $addresses
} | ConvertTo-Json -Depth 5 -Compress
"""

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [], []

    if result.returncode != 0 or not result.stdout.strip():
        return [], []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [], []

    if not isinstance(data, dict):
        return [], []

    adapters = [
        item for item in _as_list(data.get("adapters"))
        if isinstance(item, dict)
    ]
    addresses = [
        item for item in _as_list(data.get("addresses"))
        if isinstance(item, dict)
    ]

    return adapters, addresses


def _get_address_type(family: int) -> AddressType | None:
    if family == socket.AF_INET:
        return AddressType.IPV4
    if family == socket.AF_INET6:
        return AddressType.IPV6
    if family == psutil.AF_LINK:
        return AddressType.MAC
    return None


def _build_address(
    address: str,
    address_type: AddressType,
    netmask: str | None = None,
    prefix_length: int | None = None,
    broadcast: str | None = None,
) -> InterfaceAddress:
    if address_type == AddressType.MAC:
        return InterfaceAddress(
            address=address.upper(),
            address_type=address_type,
        )

    clean_address = address.split("%", 1)[0]

    try:
        parsed_address = ip_address(clean_address)
    except ValueError:
        return InterfaceAddress(
            address=address,
            address_type=address_type,
        )

    network = None
    calculated_prefix = prefix_length

    try:
        if prefix_length is not None:
            interface = ip_interface(
                f"{clean_address}/{prefix_length}"
            )
        elif netmask:
            interface = ip_interface(
                f"{clean_address}/{netmask}"
            )
        else:
            interface = None

        if interface is not None:
            calculated_prefix = interface.network.prefixlen
            network = str(interface.network)
    except ValueError:
        pass

    return InterfaceAddress(
        address=address,
        address_type=address_type,
        netmask=netmask,
        prefix_length=calculated_prefix,
        network=network,
        broadcast=broadcast,
        is_link_local=parsed_address.is_link_local,
    )


def _get_interface_mac(
    addresses: tuple[InterfaceAddress, ...],
) -> str | None:
    for address in addresses:
        if address.address_type == AddressType.MAC:
            return address.address
    return None


def _get_windows_address_type(value) -> AddressType | None:
    if value in (2, "2", "IPv4"):
        return AddressType.IPV4
    if value in (23, "23", "IPv6"):
        return AddressType.IPV6
    return None


def _parse_link_speed(value) -> int | None:
    if not isinstance(value, str):
        return None

    parts = value.strip().split()
    if len(parts) != 2:
        return None

    try:
        speed = float(parts[0].replace(",", "."))
    except ValueError:
        return None

    multipliers = {
        "bps": 1 / 1_000_000,
        "kbps": 1 / 1_000,
        "mbps": 1,
        "gbps": 1_000,
        "tbps": 1_000_000,
    }

    multiplier = multipliers.get(parts[1].casefold())
    if multiplier is None:
        return None

    result = int(speed * multiplier)
    return result if result > 0 else None


def _get_windows_interfaces() -> list[NetworkInterface]:
    adapters, raw_addresses = _get_windows_network_data()
    if not adapters:
        return []

    system_stats = psutil.net_if_stats()
    system_addresses = psutil.net_if_addrs()

    addresses_by_name: dict[str, list[InterfaceAddress]] = {}

    for item in raw_addresses:
        name = item.get("InterfaceAlias")
        address = item.get("IPAddress")
        address_type = _get_windows_address_type(
            item.get("AddressFamily")
        )

        if not isinstance(name, str) or not address or not address_type:
            continue

        built = _build_address(
            str(address),
            address_type,
            prefix_length=item.get("PrefixLength"),
        )
        addresses_by_name.setdefault(name, []).append(built)

    adapters_by_name = {}

    for item in adapters:
        name = item.get("Name")
        if isinstance(name, str) and name:
            adapters_by_name[name] = item

    for name in addresses_by_name:
        adapters_by_name.setdefault(name, {"Name": name})

    interfaces = []

    for name, metadata in adapters_by_name.items():
        description = metadata.get("InterfaceDescription")
        media_type = metadata.get("MediaType")
        is_virtual = metadata.get("Virtual")

        if not isinstance(is_virtual, bool):
            is_virtual = None

        stats = system_stats.get(name)
        addresses = list(addresses_by_name.get(name, []))

        if name in system_addresses:
            for raw in system_addresses[name]:
                if raw.family != psutil.AF_LINK or not raw.address:
                    continue

                if not any(
                    item.address_type == AddressType.MAC
                    for item in addresses
                ):
                    addresses.append(
                        _build_address(raw.address, AddressType.MAC)
                    )
                break

        address_tuple = tuple(addresses)
        ip_values = tuple(
            item.address for item in address_tuple
            if item.address_type in (
                AddressType.IPV4,
                AddressType.IPV6,
            )
        )

        interface_type = classify_interface(
            name=name,
            description=description,
            media_type=str(media_type) if media_type else None,
            is_virtual=is_virtual,
            addresses=ip_values,
        )

        status = metadata.get("Status")
        is_up = (
            status == "Up"
            if isinstance(status, str)
            else bool(stats and stats.isup)
        )

        speed = _parse_link_speed(metadata.get("LinkSpeed"))
        if speed is None and stats and stats.speed > 0:
            speed = stats.speed

        interface_index = metadata.get("ifIndex")
        if not isinstance(interface_index, int):
            interface_index = _get_interface_index(name)

        interfaces.append(
            NetworkInterface(
                name=name,
                interface_type=interface_type,
                interface_index=interface_index,
                description=description,
                media_type=str(media_type) if media_type else None,
                is_up=is_up,
                is_virtual=is_virtual,
                is_physical=(
                    is_virtual is False
                    and interface_type in (
                        InterfaceType.ETHERNET,
                        InterfaceType.WIFI,
                    )
                ),
                speed_mbps=speed,
                mtu=stats.mtu if stats else None,
                mac_address=_get_interface_mac(address_tuple),
                addresses=address_tuple,
            )
        )

    for name, raw_list in system_addresses.items():
        if name in adapters_by_name:
            continue

        addresses = []

        for raw in raw_list:
            address_type = _get_address_type(raw.family)
            if address_type is None or not raw.address:
                continue

            addresses.append(
                _build_address(
                    raw.address,
                    address_type,
                    netmask=raw.netmask,
                    broadcast=raw.broadcast,
                )
            )

        address_tuple = tuple(addresses)
        ip_values = tuple(
            item.address for item in address_tuple
            if item.address_type in (
                AddressType.IPV4,
                AddressType.IPV6,
            )
        )

        interface_type = classify_interface(
            name=name,
            addresses=ip_values,
        )

        if interface_type != InterfaceType.LOOPBACK:
            continue

        stats = system_stats.get(name)

        interfaces.append(
            NetworkInterface(
                name=name,
                interface_type=InterfaceType.LOOPBACK,
                interface_index=_get_interface_index(name),
                is_up=bool(stats and stats.isup),
                is_physical=False,
                speed_mbps=(
                    stats.speed
                    if stats and stats.speed > 0
                    else None
                ),
                mtu=stats.mtu if stats else None,
                addresses=address_tuple,
            )
        )

    return interfaces


def _get_psutil_interfaces() -> list[NetworkInterface]:
    system_addresses = psutil.net_if_addrs()
    system_stats = psutil.net_if_stats()

    interfaces = []

    for name, raw_addresses in system_addresses.items():
        stats = system_stats.get(name)
        addresses = []

        for raw in raw_addresses:
            address_type = _get_address_type(raw.family)
            if address_type is None or not raw.address:
                continue

            addresses.append(
                _build_address(
                    raw.address,
                    address_type,
                    netmask=raw.netmask,
                    broadcast=raw.broadcast,
                )
            )

        address_tuple = tuple(addresses)
        ip_values = tuple(
            item.address for item in address_tuple
            if item.address_type in (
                AddressType.IPV4,
                AddressType.IPV6,
            )
        )

        interfaces.append(
            NetworkInterface(
                name=name,
                interface_type=classify_interface(
                    name=name,
                    addresses=ip_values,
                ),
                interface_index=_get_interface_index(name),
                is_up=bool(stats and stats.isup),
                speed_mbps=(
                    stats.speed
                    if stats and stats.speed > 0
                    else None
                ),
                mtu=stats.mtu if stats else None,
                mac_address=_get_interface_mac(address_tuple),
                addresses=address_tuple,
            )
        )

    return interfaces


def get_network_interfaces() -> list[NetworkInterface]:
    """Detect network interfaces available to the operating system."""

    if platform.system() == "Windows":
        interfaces = _get_windows_interfaces()
        if interfaces:
            return interfaces

    return _get_psutil_interfaces()


def get_network_interface(name: str) -> NetworkInterface | None:
    """Get a network interface by its system name."""

    if not name:
        return None

    return next(
        (
            interface
            for interface in get_network_interfaces()
            if interface.name == name
        ),
        None,
    )
