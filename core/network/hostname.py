
import socket


def resolve_hostname(ip_address: str) -> str | None:
    """Resolve a hostname using reverse DNS."""

    if not ip_address:
        return None

    try:
        hostname, _, _ = socket.gethostbyaddr(ip_address)
    except (socket.herror, socket.gaierror, OSError):
        return None

    hostname = hostname.strip().rstrip(".")

    if not hostname:
        return None

    return hostname
