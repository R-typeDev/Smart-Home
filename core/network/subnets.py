
from dataclasses import dataclass
from ipaddress import IPv4Network, ip_interface

from core.network.interfaces.detector import get_network_interfaces
from core.network.interfaces.models import AddressType, NetworkInterface
from core.network.interfaces.policy import evaluate_interface


@dataclass(frozen=True, slots=True)
class NetworkSubnet:
    interface_name: str
    interface_type: str
    ip_address: str
    network: str
    prefix_length: int


def get_interface_subnets(
    interface: NetworkInterface,
) -> tuple[NetworkSubnet, ...]:
    """Get usable IPv4 subnets for one scannable interface."""

    decision = evaluate_interface(interface)

    if not decision.allowed:
        return ()

    subnets: list[NetworkSubnet] = []

    for address in interface.addresses:
        if address.address_type != AddressType.IPV4:
            continue

        if address.is_link_local or address.prefix_length is None:
            continue

        try:
            interface_address = ip_interface(
                f"{address.address}/{address.prefix_length}"
            )
        except ValueError:
            continue

        network = interface_address.network

        if not isinstance(network, IPv4Network):
            continue

        if network.is_link_local or network.is_loopback:
            continue

        subnets.append(
            NetworkSubnet(
                interface_name=interface.name,
                interface_type=interface.interface_type.value,
                ip_address=str(interface_address.ip),
                network=str(network),
                prefix_length=network.prefixlen,
            )
        )

    return tuple(subnets)


def get_network_subnets() -> tuple[NetworkSubnet, ...]:
    """Get unique IPv4 subnets from all eligible interfaces."""

    interfaces = get_network_interfaces()

    unique_subnets: dict[tuple[str, str], NetworkSubnet] = {}

    for interface in interfaces:
        for subnet in get_interface_subnets(interface):
            key = (subnet.interface_name, subnet.network)
            unique_subnets[key] = subnet

    return tuple(unique_subnets.values())
