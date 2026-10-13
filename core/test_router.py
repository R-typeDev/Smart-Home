
from getpass import getpass

from integrations.tplink_router.router import TPLinkRouterIntegration


def main():
    password = getpass("Password for router administrator: ")

    integration = TPLinkRouterIntegration(
        host="http://192.168.0.1",
        username="admin",
        password=password,
    )

    print("\nChecking router availability...")

    if integration.is_online():
        print("Router is reachable.")
    else:
        print("No ping response from router.")
        print("DHCP query will still be attempted.")

    try:
        clients = integration.get_dhcp_clients()

        print(f"\nDHCP leases found: {len(clients)}\n")

        for client in clients:
            print(f"Name:       {client['name']}")
            print(f"IP:         {client['ip']}")
            print(f"MAC:        {client['mac']}")
            print(f"Lease time: {client['lease_time']}")
            print("-" * 35)

    except Exception as error:
        print(f"\nError: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
