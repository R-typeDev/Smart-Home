
from dataclasses import asdict, dataclass

from tplinkrouterc6u import TplinkRouter


@dataclass
class DHCPClient:
    name: str
    ip: str
    mac: str
    lease_time: str


class TPLinkRouterIntegration:
    """Read-only integration with a TP-Link router."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        timeout: int = 15,
    ):
        self.host = host
        self.username = username
        self._password = password
        self.timeout = timeout

    def get_dhcp_clients(self) -> list[dict]:
        router = TplinkRouter(
            host=self.host,
            username=self.username,
            password=self._password,
            timeout=self.timeout,
        )

        try:
            router.authorize()
            leases = router.get_ipv4_dhcp_leases()

            clients = [
                DHCPClient(
                    name=lease.hostname or "",
                    ip=str(lease._ipaddr),
                    mac=str(lease._macaddr),
                    lease_time=lease.lease_time,
                )
                for lease in leases
            ]

            return [asdict(client) for client in clients]

        finally:
            router.logout()
