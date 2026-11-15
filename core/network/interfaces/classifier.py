from ipaddress import ip_address

from core.network.interfaces.models import InterfaceType


SYSTEM_KEYWORDS = (
    "wan miniport",
    "kernel debug",
    "teredo",
    "ip-https",
    "6to4",
    "loopback",
)

VPN_KEYWORDS = (
    "vpn",
    "proton",
    "veepn",
    "openvpn",
    "wireguard",
    "wintun",
    "tap adapter",
    "tun adapter",
    "tunnel",
)

WIFI_DIRECT_KEYWORDS = (
    "wi-fi direct",
    "wifi direct",
)

WIFI_KEYWORDS = (
    "wireless",
    "wi-fi",
    "wifi",
    "802.11",
)

ETHERNET_KEYWORDS = (
    "ethernet",
    "realtek pcie gbe",
    "gigabit ethernet",
)


def _contains_keyword(value: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in value for keyword in keywords)


def _has_loopback_address(addresses: tuple[str, ...]) -> bool:
    for value in addresses:
        try:
            address = ip_address(value.split("%", 1)[0])
        except ValueError:
            continue

        if address.is_loopback:
            return True

    return False


def classify_interface(
    name: str,
    description: str | None = None,
    media_type: str | None = None,
    is_virtual: bool | None = None,
    addresses: tuple[str, ...] = (),
) -> InterfaceType:
    """Classify an interface using operating-system metadata."""

    values = " ".join(
        value for value in (name, description, media_type) if value
    ).casefold()

    if "loopback" in values or _has_loopback_address(addresses):
        return InterfaceType.LOOPBACK

    if _contains_keyword(values, SYSTEM_KEYWORDS):
        return InterfaceType.SYSTEM

    if _contains_keyword(values, VPN_KEYWORDS):
        return InterfaceType.VPN

    if _contains_keyword(values, WIFI_DIRECT_KEYWORDS):
        return InterfaceType.VIRTUAL

    if _contains_keyword(values, WIFI_KEYWORDS):
        return (
            InterfaceType.VIRTUAL
            if is_virtual is True
            else InterfaceType.WIFI
        )

    if _contains_keyword(values, ETHERNET_KEYWORDS):
        return (
            InterfaceType.VIRTUAL
            if is_virtual is True
            else InterfaceType.ETHERNET
        )

    if is_virtual is True:
        return InterfaceType.VIRTUAL

    if is_virtual is False and media_type:
        media = media_type.casefold()

        if "802.3" in media:
            return InterfaceType.ETHERNET

        if "802.11" in media or "native 802.11" in media:
            return InterfaceType.WIFI

    return InterfaceType.UNKNOWN