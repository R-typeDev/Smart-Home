
import socket
from dataclasses import dataclass
from ipaddress import IPv4Address

from core.network.arp import get_arp_table
from core.network.hostname import resolve_hostname
from core.network.interfaces.detector import get_network_interfaces
from core.network.interfaces.models import AddressType
from core.network.mdns import discover_mdns_records
from core.network.netbios import resolve_netbios_name
from core.network.scanner import scan_network
from core.network.ssdp import (
    SsdpDevice,
    discover_ssdp_devices,
)
from core.network.upnp import (
    UpnpDeviceDescription,
    discover_upnp_devices,
)


@dataclass(frozen=True, slots=True)
class DiscoveredHost:
    ip_address: str

    mac_address: str | None = None
    hostname: str | None = None

    local_interface_name: str | None = None
    local_interface_index: int | None = None

    connection_type: str = "unknown"

    is_available: bool = False
    is_local: bool = False

    arp_state: str | None = None

    discovery_methods: tuple[str, ...] = ()

    ssdp_responses: tuple[SsdpDevice, ...] = ()
    upnp_descriptions: tuple[UpnpDeviceDescription, ...] = ()


def _normalize_dns_name(name: str) -> str:
    return name.rstrip(".").lower()


def _extract_mdns_data(records):
    """Extract IPv4 addresses, hostnames and MAC addresses from mDNS."""

    addresses = {}
    hostnames = {}
    mac_addresses = {}

    for record in records:
        if record.record_type != "A":
            continue

        name = _normalize_dns_name(record.name)

        try:
            IPv4Address(record.value)
        except ValueError:
            continue

        addresses[name] = record.value
        hostnames[name] = record.name.rstrip(".").split(".")[0]

    for record in records:
        if record.record_type != "SRV":
            continue

        parts = record.value.split()

        if not parts:
            continue

        target = _normalize_dns_name(parts[-1])

        if target not in addresses:
            continue

        instance = _normalize_dns_name(record.name)
        host_ip = addresses[target]

        hostnames[host_ip] = hostnames.get(
            target,
            target.split(".")[0],
        )

        for txt_record in records:
            if (
                txt_record.record_type != "TXT"
                or _normalize_dns_name(txt_record.name) != instance
            ):
                continue

            for item in txt_record.value.split(";"):
                key, separator, value = item.strip().partition("=")

                if separator and key.strip().lower() == "mac":
                    mac = value.strip().lower()

                    if mac:
                        mac_addresses[host_ip] = mac

    return addresses, hostnames, mac_addresses


def discover_hosts(
    max_workers: int = 32,
    max_hosts: int = 4096,
) -> tuple[DiscoveredHost, ...]:
    """Discover network hosts and their available services."""

    hosts: dict[str, dict] = {}

    def get_host(ip: str) -> dict:
        return hosts.setdefault(
            ip,
            {
                "ip_address": ip,
                "mac_address": None,
                "hostname": None,
                "local_interface_name": None,
                "local_interface_index": None,
                "connection_type": "unknown",
                "is_available": False,
                "is_local": False,
                "arp_state": None,
                "discovery_methods": set(),
                "ssdp_responses": [],
                "upnp_descriptions": [],
            },
        )

    # 1. ICMP discovery.
    try:
        scan_results = scan_network(
            max_workers=max_workers,
            max_hosts=max_hosts,
        )
    except Exception:
        scan_results = ()

    for result in scan_results:
        host = get_host(result.ip_address)

        if result.is_available:
            host["is_available"] = True

        host["discovery_methods"].add("icmp")

    # 2. Detect local network interfaces.
    try:
        interfaces = get_network_interfaces()
    except Exception:
        interfaces = ()

    interface_names = {
        interface.interface_index: interface.name
        for interface in interfaces
        if interface.interface_index is not None
    }

    # 3. ARP neighbor table.
    try:
        arp_entries = get_arp_table()
    except Exception:
        arp_entries = ()

    for entry in arp_entries:
        host = get_host(entry.ip_address)

        host["mac_address"] = (
            host["mac_address"] or entry.mac_address
        )

        if host["local_interface_index"] is None:
            host["local_interface_index"] = entry.interface_index

        if host["local_interface_name"] is None:
            host["local_interface_name"] = (
                interface_names.get(entry.interface_index)
                or entry.interface_name
            )

        host["arp_state"] = entry.state
        host["discovery_methods"].add("arp")

    # 4. Local computer addresses.
    hostname = socket.gethostname()

    for interface in interfaces:
        if not interface.is_up or interface.is_loopback:
            continue

        for address in interface.addresses:
            if address.address_type != AddressType.IPV4:
                continue

            if address.is_link_local:
                continue

            host = get_host(address.address)

            host["mac_address"] = (
                interface.mac_address or host["mac_address"]
            )
            host["hostname"] = hostname
            host["local_interface_name"] = interface.name
            host["local_interface_index"] = interface.interface_index
            host["is_local"] = True
            host["is_available"] = True
            host["discovery_methods"].add("local_interface")

    # 5. Reverse DNS.
    for host in hosts.values():
        if host["hostname"] is not None:
            continue

        try:
            resolved_hostname = resolve_hostname(host["ip_address"])
        except Exception:
            resolved_hostname = None

        if resolved_hostname:
            host["hostname"] = resolved_hostname
            host["discovery_methods"].add("reverse_dns")

    # 6. mDNS discovery.
    try:
        mdns_records = discover_mdns_records()
        addresses, hostnames, mac_addresses = _extract_mdns_data(
            mdns_records
        )
    except Exception:
        addresses, hostnames, mac_addresses = {}, {}, {}

    for name, ip in addresses.items():
        host = get_host(ip)

        host["is_available"] = True
        host["discovery_methods"].add("mdns")

        if not host["is_local"]:
            mdns_hostname = hostnames.get(name)

            if mdns_hostname and not host["hostname"]:
                host["hostname"] = mdns_hostname

        if not host["mac_address"]:
            host["mac_address"] = mac_addresses.get(ip)

    # 7. NetBIOS discovery.
    for host in hosts.values():
        if host["hostname"] is not None:
            continue

        try:
            netbios_name = resolve_netbios_name(host["ip_address"])
        except Exception:
            netbios_name = None

        if netbios_name:
            host["hostname"] = netbios_name
            host["discovery_methods"].add("netbios")

    # 8. SSDP discovery.
    try:
        ssdp_devices = discover_ssdp_devices()
    except Exception:
        ssdp_devices = ()

    for device in ssdp_devices:
        host = get_host(device.ip_address)

        host["is_available"] = True
        host["discovery_methods"].add("ssdp")
        host["ssdp_responses"].append(device)

    # 9. UPnP descriptions.
    try:
        upnp_result = discover_upnp_devices(
            ssdp_results=ssdp_devices,
        )
        upnp_descriptions = upnp_result.devices
    except Exception:
        upnp_descriptions = ()

    for description in upnp_descriptions:
        host = get_host(description.ip_address)

        host["is_available"] = True
        host["discovery_methods"].add("upnp")
        host["upnp_descriptions"].append(description)

    # 10. Build immutable results.
    discovered_hosts = []

    for host in hosts.values():
        discovered_hosts.append(
            DiscoveredHost(
                ip_address=host["ip_address"],
                mac_address=host["mac_address"],
                hostname=host["hostname"],
                local_interface_name=host["local_interface_name"],
                local_interface_index=host["local_interface_index"],
                connection_type=host["connection_type"],
                is_available=host["is_available"],
                is_local=host["is_local"],
                arp_state=host["arp_state"],
                discovery_methods=tuple(
                    sorted(host["discovery_methods"])
                ),
                ssdp_responses=tuple(host["ssdp_responses"]),
                upnp_descriptions=tuple(
                    host["upnp_descriptions"]
                ),
            )
        )

    return tuple(
        sorted(
            discovered_hosts,
            key=lambda host: IPv4Address(host.ip_address),
        )
    )
