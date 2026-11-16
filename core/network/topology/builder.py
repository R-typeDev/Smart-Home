
import ipaddress

from core.network.discovery import discover_hosts
from core.network.interfaces.detector import get_network_interfaces
from core.network.subnets import get_network_subnets

from .models import (
    DeviceNode,
    GatewayNode,
    InterfaceNode,
    LinkType,
    NetworkLink,
    NetworkTopology,
    SubnetNode,
)
from .routes import get_default_routes


def _interface_id(interface) -> str:
    if interface.interface_index is not None:
        return f"interface:{interface.interface_index}"

    return f"interface:{interface.name}"


def _get_interface_ip_addresses(interface) -> list[str]:
    addresses = []

    for address in interface.addresses:
        address_type = getattr(
            address.address_type,
            "value",
            address.address_type,
        )

        if str(address_type).lower() == "ipv4":
            addresses.append(address.address)

    return addresses


def _build_interfaces(topology: NetworkTopology, interfaces):
    interface_map = {}

    for interface in interfaces:
        interface_id = _interface_id(interface)

        node = InterfaceNode(
            id=interface_id,
            name=interface.name,
            interface_type=str(
                getattr(interface.interface_type, "value", interface.interface_type)
            ),
            interface_index=interface.interface_index,
            ip_addresses=_get_interface_ip_addresses(interface),
            mac_address=interface.mac_address,
            is_up=interface.is_up,
            is_virtual=interface.is_virtual,
        )

        topology.interfaces.append(node)
        interface_map[interface.name] = node

    return interface_map


def _build_subnets(topology: NetworkTopology, subnets, interface_map):
    subnet_map = {}

    for subnet in subnets:
        interface = interface_map.get(subnet.interface_name)

        if interface is None:
            continue

        subnet_id = f"subnet:{interface.id}:{subnet.network}"

        node = SubnetNode(
            id=subnet_id,
            network=subnet.network,
            interface_id=interface.id,
            interface_name=subnet.interface_name,
            prefix_length=subnet.prefix_length,
        )

        topology.subnets.append(node)
        subnet_map[subnet_id] = node

        topology.links.append(
            NetworkLink(
                source_id=interface.id,
                target_id=subnet_id,
                link_type=LinkType.INTERFACE_SUBNET,
                evidence="Local interface address and subnet configuration",
                confidence=1.0,
                is_confirmed=True,
            )
        )

    return subnet_map


def _build_gateways(topology: NetworkTopology, routes, interfaces):
    gateway_map = {}

    interfaces_by_index = {
        interface.interface_index: interface
        for interface in interfaces
        if interface.interface_index is not None
    }

    interfaces_by_name = {
        interface.name: interface
        for interface in interfaces
    }

    for route in routes:
        if not route.next_hop:
            continue

        interface = None

        if route.interface_index is not None:
            interface = interfaces_by_index.get(route.interface_index)

        if interface is None and route.interface_name:
            interface = interfaces_by_name.get(route.interface_name)

        if interface is None:
            continue

        interface_id = _interface_id(interface)
        gateway_id = f"gateway:{route.next_hop}:{interface_id}"

        if gateway_id in gateway_map:
            continue

        node = GatewayNode(
            id=gateway_id,
            ip_address=route.next_hop,
            interface_id=interface_id,
            interface_name=interface.name,
            interface_index=interface.interface_index,
            is_default=route.is_default,
        )

        topology.gateways.append(node)
        gateway_map[gateway_id] = node

    return gateway_map


def _build_devices(topology: NetworkTopology, hosts, gateway_ips):
    device_map = {}

    for host in hosts:
        if host.is_local:
            continue

        if host.ip_address in gateway_ips:
            continue

        device_id = f"device:{host.ip_address}"

        node = DeviceNode(
            id=device_id,
            ip_address=host.ip_address,
            mac_address=host.mac_address,
            hostname=host.hostname,
            is_available=host.is_available,
            is_local=host.is_local,
            connection_type=host.connection_type,
            discovery_methods=list(host.discovery_methods),
        )

        device_map[device_id] = node

    topology.devices.extend(device_map.values())

    return device_map


def _build_subnet_device_links(
    topology: NetworkTopology,
    subnet_map,
    device_map,
):
    for subnet in subnet_map.values():
        try:
            subnet_network = ipaddress.ip_network(
                subnet.network,
                strict=False,
            )
        except ValueError:
            continue

        for device in device_map.values():
            try:
                device_ip = ipaddress.ip_address(device.ip_address)
            except ValueError:
                continue

            if device_ip not in subnet_network:
                continue

            topology.links.append(
                NetworkLink(
                    source_id=subnet.id,
                    target_id=device.id,
                    link_type=LinkType.SUBNET_DEVICE,
                    evidence=(
                        f"Discovered device address {device.ip_address} "
                        f"belongs to subnet {subnet.network}"
                    ),
                    confidence=1.0,
                    is_confirmed=True,
                )
            )


def _build_subnet_gateway_links(
    topology: NetworkTopology,
    subnet_map,
    gateway_map,
):
    for gateway in gateway_map.values():
        try:
            gateway_ip = ipaddress.ip_address(gateway.ip_address)
        except ValueError:
            continue

        for subnet in subnet_map.values():
            if subnet.interface_id != gateway.interface_id:
                continue

            try:
                subnet_network = ipaddress.ip_network(
                    subnet.network,
                    strict=False,
                )
            except ValueError:
                continue

            if gateway_ip not in subnet_network:
                continue

            topology.links.append(
                NetworkLink(
                    source_id=subnet.id,
                    target_id=gateway.id,
                    link_type=LinkType.SUBNET_GATEWAY,
                    evidence=(
                        f"System routing table identifies "
                        f"{gateway.ip_address} as a next hop "
                        f"through {gateway.interface_name}"
                    ),
                    confidence=1.0,
                    is_confirmed=True,
                )
            )


def build_network_topology() -> NetworkTopology:
    topology = NetworkTopology()

    # Collect network data once and reuse it.
    interfaces = get_network_interfaces()
    subnets = get_network_subnets(interfaces)

    hosts = discover_hosts(
        interfaces=interfaces,
        subnets=subnets,
    )

    routes = get_default_routes()

    interface_map = _build_interfaces(
        topology,
        interfaces,
    )

    subnet_map = _build_subnets(
        topology,
        subnets,
        interface_map,
    )

    gateway_map = _build_gateways(
        topology,
        routes,
        interfaces,
    )

    gateway_ips = {
        gateway.ip_address
        for gateway in gateway_map.values()
    }

    device_map = _build_devices(
        topology,
        hosts,
        gateway_ips,
    )

    _build_subnet_device_links(
        topology,
        subnet_map,
        device_map,
    )

    _build_subnet_gateway_links(
        topology,
        subnet_map,
        gateway_map,
    )

    return topology
