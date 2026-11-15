
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network

from core.network.interfaces.models import NetworkInterface
from core.network.ping import ping
from core.network.subnets import NetworkSubnet, get_network_subnets


@dataclass(frozen=True, slots=True)
class ScanResult:
    ip_address: str
    is_available: bool
    discovery_method: str = "icmp"


def _check_host(address: IPv4Address) -> ScanResult | None:
    """Check one host and return a result if it responds."""

    if ping(str(address)):
        return ScanResult(
            ip_address=str(address),
            is_available=True,
        )

    return None


def scan_subnet(
    subnet: NetworkSubnet,
    max_workers: int = 32,
    max_hosts: int = 4096,
) -> tuple[ScanResult, ...]:
    """Scan one IPv4 subnet using bounded concurrent ICMP requests."""

    if max_workers < 1:
        raise ValueError("max_workers must be greater than zero")

    if max_hosts < 1:
        raise ValueError("max_hosts must be greater than zero")

    network = ip_network(subnet.network, strict=False)

    if not isinstance(network, IPv4Network):
        raise ValueError("Only IPv4 networks are supported")

    if network.num_addresses > max_hosts:
        raise ValueError(
            f"Subnet contains {network.num_addresses} addresses; "
            f"maximum allowed is {max_hosts}"
        )

    addresses = iter(network.hosts())
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pending = set()

        def submit_next() -> bool:
            try:
                address = next(addresses)
            except StopIteration:
                return False

            pending.add(executor.submit(_check_host, address))
            return True

        for _ in range(max_workers):
            if not submit_next():
                break

        while pending:
            completed, pending = wait(
                pending,
                return_when=FIRST_COMPLETED,
            )

            for future in completed:
                result = future.result()

                if result is not None:
                    results.append(result)

                submit_next()

    return tuple(
        sorted(
            results,
            key=lambda result: ip_address(result.ip_address),
        )
    )


def scan_network(
    max_workers: int = 32,
    max_hosts: int = 4096,
    interfaces: list[NetworkInterface] | tuple[NetworkInterface, ...] | None = None,
    subnets: tuple[NetworkSubnet, ...] | None = None,
) -> tuple[ScanResult, ...]:
    """Scan all eligible local IPv4 subnets."""

    if max_workers < 1:
        raise ValueError("max_workers must be greater than zero")

    if max_hosts < 1:
        raise ValueError("max_hosts must be greater than zero")

    if subnets is None:
        subnets = get_network_subnets(interfaces)

    results: dict[str, ScanResult] = {}

    for subnet in subnets:
        subnet_results = scan_subnet(
            subnet,
            max_workers=max_workers,
            max_hosts=max_hosts,
        )

        for result in subnet_results:
            results[result.ip_address] = result

    return tuple(
        sorted(
            results.values(),
            key=lambda result: ip_address(result.ip_address),
        )
    )
