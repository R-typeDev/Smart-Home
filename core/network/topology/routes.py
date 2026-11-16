
import json
import platform
import re
import socket
import subprocess
from dataclasses import dataclass


@dataclass
class NetworkRoute:
    destination: str
    next_hop: str | None
    interface_index: int | None
    interface_name: str | None
    metric: int | None = None
    is_default: bool = False


def _run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )

    if result.returncode != 0:
        return ""

    return result.stdout


def _get_interface_index(interface_name: str | None) -> int | None:
    if not interface_name:
        return None

    try:
        return socket.if_nametoindex(interface_name)
    except OSError:
        return None


def _get_windows_routes() -> list[NetworkRoute]:
    script = (
        "Get-NetRoute -AddressFamily IPv4 | "
        "Select-Object DestinationPrefix, NextHop, "
        "InterfaceIndex, RouteMetric | "
        "ConvertTo-Json -Compress"
    )

    output = _run_command([
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        script,
    ])

    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    if isinstance(data, dict):
        data = [data]

    routes = []

    for item in data:
        destination = item.get("DestinationPrefix")
        next_hop = item.get("NextHop")
        interface_index = item.get("InterfaceIndex")
        metric = item.get("RouteMetric")

        if not destination:
            continue

        try:
            interface_index = int(interface_index)
        except (TypeError, ValueError):
            interface_index = None

        try:
            metric = int(metric)
        except (TypeError, ValueError):
            metric = None

        next_hop = (
            next_hop
            if next_hop and next_hop != "0.0.0.0"
            else None
        )

        routes.append(
            NetworkRoute(
                destination=destination,
                next_hop=next_hop,
                interface_index=interface_index,
                interface_name=None,
                metric=metric,
                is_default=destination == "0.0.0.0/0",
            )
        )

    return routes


def _get_linux_routes() -> list[NetworkRoute]:
    output = _run_command(["ip", "-j", "-4", "route", "show"])

    if not output:
        return []

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return []

    routes = []

    for item in data:
        destination = item.get("dst", "default")

        is_default = destination in ("default", "0.0.0.0/0")

        if is_default:
            destination = "0.0.0.0/0"

        next_hop = item.get("gateway")
        interface_name = item.get("dev")
        metric = item.get("metric")

        interface_index = _get_interface_index(interface_name)

        try:
            metric = int(metric) if metric is not None else None
        except (TypeError, ValueError):
            metric = None

        routes.append(
            NetworkRoute(
                destination=destination,
                next_hop=next_hop,
                interface_index=interface_index,
                interface_name=interface_name,
                metric=metric,
                is_default=is_default,
            )
        )

    return routes


def _get_macos_routes() -> list[NetworkRoute]:
    output = _run_command(["netstat", "-rn", "-f", "inet"])

    if not output:
        return []

    routes = []

    for line in output.splitlines():
        parts = line.split()

        if len(parts) < 4:
            continue

        destination, gateway, flags, interface_name = parts[:4]

        if destination == "default":
            destination = "0.0.0.0/0"

        elif re.fullmatch(r"\d+\.\d+\.\d+\.\d+", destination):
            destination = f"{destination}/32"

        elif "/" not in destination:
            continue

        is_default = destination == "0.0.0.0/0"

        next_hop = (
            None
            if gateway in ("link#0", "0.0.0.0")
            else gateway
        )

        routes.append(
            NetworkRoute(
                destination=destination,
                next_hop=next_hop,
                interface_index=_get_interface_index(interface_name),
                interface_name=interface_name,
                is_default=is_default,
            )
        )

    return routes


def get_network_routes() -> list[NetworkRoute]:
    system = platform.system()

    try:
        if system == "Windows":
            return _get_windows_routes()

        if system == "Linux":
            return _get_linux_routes()

        if system == "Darwin":
            return _get_macos_routes()

    except (OSError, subprocess.TimeoutExpired):
        return []

    return []


def get_default_routes() -> list[NetworkRoute]:
    return [
        route
        for route in get_network_routes()
        if route.is_default and route.next_hop
    ]


def get_default_gateways() -> list[str]:
    return list(
        dict.fromkeys(
            route.next_hop
            for route in get_default_routes()
            if route.next_hop
        )
    )
