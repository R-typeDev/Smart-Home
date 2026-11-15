
import json
import platform
import re
import socket
import subprocess
from dataclasses import dataclass
from ipaddress import IPv4Address, ip_address


@dataclass(frozen=True, slots=True)
class ArpEntry:
    ip_address: str
    mac_address: str
    interface_name: str | None = None
    interface_index: int | None = None
    state: str | None = None
    discovery_method: str = "arp"


_INVALID_STATES = {
    "FAILED",
    "INCOMPLETE",
    "UNREACHABLE",
    "PERMANENT_INCOMPLETE",
}

_MAC_PATTERN = re.compile(
    r"^(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$"
)

_MACOS_ARP_PATTERN = re.compile(
    r"\((?P<ip>\d{1,3}(?:\.\d{1,3}){3})\)"
    r"\s+at\s+(?P<mac>[0-9a-fA-F:.-]+)"
    r"\s+on\s+(?P<interface>\S+)"
)


def _normalize_mac(value: str) -> str | None:
    if not value:
        return None

    value = value.strip().replace("-", ":")

    if not _MAC_PATTERN.fullmatch(value):
        return None

    octets = bytes.fromhex(value.replace(":", ""))

    if all(octet == 0 for octet in octets):
        return None

    if all(octet == 255 for octet in octets):
        return None

    if octets[0] & 1:
        return None

    return ":".join(f"{octet:02x}" for octet in octets)


def _normalize_ip(value: str) -> str | None:
    try:
        address = ip_address(value)
    except ValueError:
        return None

    if not isinstance(address, IPv4Address):
        return None

    if (
        address.is_unspecified
        or address.is_loopback
        or address.is_multicast
    ):
        return None

    return str(address)


def _normalize_interface_index(value: object) -> int | None:
    if value is None:
        return None

    try:
        index = int(value)
    except (TypeError, ValueError):
        return None

    return index if index > 0 else None


def _get_interface_name(index: int | None) -> str | None:
    if index is None:
        return None

    try:
        return socket.if_indextoname(index)
    except (OSError, ValueError, AttributeError):
        return None


def _get_interface_index(name: str | None) -> int | None:
    if not name:
        return None

    try:
        return socket.if_nametoindex(name)
    except (OSError, ValueError):
        return None


def _create_entry(
    ip: str,
    mac: str,
    interface_name: str | None = None,
    interface_index: int | None = None,
    state: str | None = None,
) -> ArpEntry | None:
    normalized_ip = _normalize_ip(ip)
    normalized_mac = _normalize_mac(mac)

    if normalized_ip is None or normalized_mac is None:
        return None

    normalized_index = _normalize_interface_index(
        interface_index
    )

    normalized_name = interface_name or _get_interface_name(
        normalized_index
    )

    if normalized_index is None:
        normalized_index = _get_interface_index(normalized_name)

    normalized_state = (
        str(state).strip().upper()
        if state is not None
        else None
    )

    if normalized_state in _INVALID_STATES:
        return None

    return ArpEntry(
        ip_address=normalized_ip,
        mac_address=normalized_mac,
        interface_name=normalized_name,
        interface_index=normalized_index,
        state=normalized_state or None,
    )


def _sort_entries(entries: dict) -> tuple[ArpEntry, ...]:
    return tuple(
        sorted(
            entries.values(),
            key=lambda item: (
                IPv4Address(item.ip_address),
                item.interface_index or 0,
                item.interface_name or "",
            ),
        )
    )


def _read_windows_arp_table() -> tuple[ArpEntry, ...]:
    script = r"""
$ErrorActionPreference = 'Stop'

$items = @(
    Get-NetNeighbor -AddressFamily IPv4 -ErrorAction Stop |
    Select-Object IPAddress, LinkLayerAddress, InterfaceIndex,
        @{Name='State'; Expression={$_.State.ToString()}}
)

ConvertTo-Json -InputObject $items -Compress -Depth 3
"""

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

    if result.returncode != 0:
        raise RuntimeError(
            f"Windows ARP query failed: {result.stderr.strip()}"
        )

    output = result.stdout.strip()

    if not output:
        return ()

    try:
        data = json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Invalid JSON returned by Windows ARP query"
        ) from error

    if isinstance(data, dict):
        data = [data]

    entries = {}

    for item in data:
        if not isinstance(item, dict):
            continue

        index = _normalize_interface_index(
            item.get("InterfaceIndex")
        )

        entry = _create_entry(
            ip=item.get("IPAddress", ""),
            mac=item.get("LinkLayerAddress", ""),
            interface_index=index,
            state=item.get("State"),
        )

        if entry is not None:
            key = (entry.ip_address, entry.interface_index)
            entries[key] = entry

    return _sort_entries(entries)


def _read_linux_arp_table() -> tuple[ArpEntry, ...]:
    result = subprocess.run(
        ["ip", "-j", "neigh", "show"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Linux ARP query failed: {result.stderr.strip()}"
        )

    output = result.stdout.strip()

    if not output:
        return ()

    try:
        data = json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Invalid JSON returned by Linux neighbor query"
        ) from error

    entries = {}

    for item in data:
        if not isinstance(item, dict):
            continue

        interface_name = item.get("dev")
        interface_index = _get_interface_index(interface_name)

        states = item.get("state", [])

        if isinstance(states, str):
            states = [states]

        state = states[0] if states else None

        entry = _create_entry(
            ip=item.get("dst", ""),
            mac=item.get("lladdr", ""),
            interface_name=interface_name,
            interface_index=interface_index,
            state=state,
        )

        if entry is not None:
            key = (entry.ip_address, entry.interface_index)
            entries[key] = entry

    return _sort_entries(entries)


def _read_macos_arp_table() -> tuple[ArpEntry, ...]:
    result = subprocess.run(
        ["arp", "-an"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"macOS ARP query failed: {result.stderr.strip()}"
        )

    entries = {}

    for line in result.stdout.splitlines():
        match = _MACOS_ARP_PATTERN.search(line)

        if not match:
            continue

        interface_name = match.group("interface")

        entry = _create_entry(
            ip=match.group("ip"),
            mac=match.group("mac"),
            interface_name=interface_name,
            interface_index=_get_interface_index(interface_name),
        )

        if entry is not None:
            key = (entry.ip_address, entry.interface_index)
            entries[key] = entry

    return _sort_entries(entries)


def get_arp_table() -> tuple[ArpEntry, ...]:
    """Get the IPv4 neighbor table for the current operating system."""

    system = platform.system()

    if system == "Windows":
        return _read_windows_arp_table()

    if system == "Linux":
        return _read_linux_arp_table()

    if system == "Darwin":
        return _read_macos_arp_table()

    raise NotImplementedError(
        f"ARP table reading is not supported on {system}"
    )
