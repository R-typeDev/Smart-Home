
from dataclasses import dataclass, field
from enum import StrEnum


class InterfaceType(StrEnum):
    ETHERNET = "ethernet"
    WIFI = "wifi"
    VPN = "vpn"
    VIRTUAL = "virtual"
    SYSTEM = "system"
    LOOPBACK = "loopback"
    UNKNOWN = "unknown"


class AddressType(StrEnum):
    MAC = "mac"
    IPV4 = "ipv4"
    IPV6 = "ipv6"


@dataclass(frozen=True, slots=True)
class InterfaceAddress:
    address: str
    address_type: AddressType
    netmask: str | None = None
    prefix_length: int | None = None
    network: str | None = None
    broadcast: str | None = None
    is_link_local: bool = False


@dataclass(frozen=True, slots=True)
class NetworkInterface:
    name: str
    interface_type: InterfaceType = InterfaceType.UNKNOWN

    interface_index: int | None = None

    description: str | None = None
    media_type: str | None = None

    is_up: bool = False
    is_virtual: bool | None = None
    is_physical: bool = False

    speed_mbps: int | None = None
    mtu: int | None = None

    mac_address: str | None = None
    addresses: tuple[InterfaceAddress, ...] = field(default_factory=tuple)

    @property
    def is_loopback(self) -> bool:
        return self.interface_type == InterfaceType.LOOPBACK

    @property
    def ipv4_addresses(self) -> tuple[InterfaceAddress, ...]:
        return tuple(
            address for address in self.addresses
            if address.address_type == AddressType.IPV4
        )

    @property
    def ipv6_addresses(self) -> tuple[InterfaceAddress, ...]:
        return tuple(
            address for address in self.addresses
            if address.address_type == AddressType.IPV6
        )

    @property
    def has_usable_address(self) -> bool:
        return any(
            not address.is_link_local
            for address in (*self.ipv4_addresses, *self.ipv6_addresses)
        )
