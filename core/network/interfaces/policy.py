
from dataclasses import dataclass

from core.network.interfaces.models import (
    InterfaceType,
    NetworkInterface,
    AddressType,
)


@dataclass(frozen=True, slots=True)
class InterfaceScanDecision:
    interface_name: str
    allowed: bool
    reason: str


def evaluate_interface(
    interface: NetworkInterface,
) -> InterfaceScanDecision:
    """Determine whether an interface can be used for network scanning."""

    if interface.interface_type not in (
        InterfaceType.ETHERNET,
        InterfaceType.WIFI,
    ):
        return InterfaceScanDecision(
            interface_name=interface.name,
            allowed=False,
            reason="unsupported_interface_type",
        )

    if not interface.is_up:
        return InterfaceScanDecision(
            interface_name=interface.name,
            allowed=False,
            reason="interface_down",
        )

    usable_ipv4 = [
        address
        for address in interface.addresses
        if address.address_type == AddressType.IPV4
        and not address.is_link_local
        and address.network is not None
    ]

    if not usable_ipv4:
        return InterfaceScanDecision(
            interface_name=interface.name,
            allowed=False,
            reason="no_usable_ipv4_address",
        )

    return InterfaceScanDecision(
        interface_name=interface.name,
        allowed=True,
        reason="ready",
    )


def get_scannable_interfaces(
    interfaces: tuple[NetworkInterface, ...],
) -> tuple[NetworkInterface, ...]:
    """Return interfaces eligible for network scanning."""

    return tuple(
        interface
        for interface in interfaces
        if evaluate_interface(interface).allowed
    )
