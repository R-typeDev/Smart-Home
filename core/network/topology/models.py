
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class NodeType(StrEnum):
    INTERFACE = "interface"
    SUBNET = "subnet"
    DEVICE = "device"
    GATEWAY = "gateway"


class LinkType(StrEnum):
    INTERFACE_SUBNET = "interface_subnet"
    SUBNET_DEVICE = "subnet_device"
    SUBNET_GATEWAY = "subnet_gateway"
    DEVICE_GATEWAY = "device_gateway"


@dataclass
class InterfaceNode:
    id: str
    name: str
    interface_type: str
    interface_index: int | None = None
    ip_addresses: list[str] = field(default_factory=list)
    mac_address: str | None = None
    is_up: bool = False
    is_virtual: bool = False


@dataclass
class SubnetNode:
    id: str
    network: str
    interface_id: str
    interface_name: str
    prefix_length: int


@dataclass
class DeviceNode:
    id: str
    ip_address: str
    mac_address: str | None = None
    hostname: str | None = None
    is_available: bool = False
    is_local: bool = False
    connection_type: str = "unknown"
    discovery_methods: list[str] = field(default_factory=list)


@dataclass
class GatewayNode:
    id: str
    ip_address: str
    interface_id: str
    interface_name: str
    interface_index: int | None = None
    is_default: bool = False


@dataclass
class NetworkLink:
    source_id: str
    target_id: str
    link_type: LinkType
    evidence: str
    confidence: float = 1.0
    is_confirmed: bool = True


@dataclass
class NetworkTopology:
    interfaces: list[InterfaceNode] = field(default_factory=list)
    subnets: list[SubnetNode] = field(default_factory=list)
    devices: list[DeviceNode] = field(default_factory=list)
    gateways: list[GatewayNode] = field(default_factory=list)
    links: list[NetworkLink] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json_data(self) -> dict[str, Any]:
        data = self.to_dict()

        for link in data["links"]:
            link["link_type"] = link["link_type"].value

        return data
