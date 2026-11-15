
import ipaddress
import json
import uuid
from typing import Any

from database.connection import get_connection


VALID_NODE_STATUSES = ("online", "offline", "unknown")
VALID_CONNECTION_TYPES = ("unknown",)
VALID_SCAN_TYPES = ("manual", "automatic")
VALID_RUN_STATUSES = ("completed", "failed", "cancelled")
VALID_SETTING_TYPES = ("string", "boolean", "integer", "json")


def _require_string(
    value: Any,
    field_name: str,
    *,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    value = value.strip()

    if not allow_empty and not value:
        raise ValueError(f"{field_name} is required.")

    return value


def _validate_optional_string(
    value: Any,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _require_string(value, field_name)


def _get_node(connection, node_id: str) -> dict[str, Any] | None:
    row = connection.execute("""
        SELECT *
        FROM network_nodes
        WHERE id = ?
    """, (node_id,)).fetchone()

    if row is None:
        return None

    node = dict(row)

    addresses = connection.execute("""
        SELECT *
        FROM network_addresses
        WHERE node_id = ?
        ORDER BY is_primary DESC, ip_address
    """, (node_id,)).fetchall()

    node["addresses"] = [dict(item) for item in addresses]

    return node


def get_network_nodes() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id
            FROM network_nodes
            ORDER BY name COLLATE NOCASE, hostname COLLATE NOCASE
        """).fetchall()

        return [
            node
            for row in rows
            if (node := _get_node(connection, row["id"])) is not None
        ]


def get_network_node(node_id: str) -> dict[str, Any] | None:
    node_id = _require_string(node_id, "Node ID")

    with get_connection() as connection:
        return _get_node(connection, node_id)


def get_network_node_by_identity(
    identity_key: str,
) -> dict[str, Any] | None:
    identity_key = _require_string(identity_key, "Identity key")

    with get_connection() as connection:
        row = connection.execute("""
            SELECT id
            FROM network_nodes
            WHERE identity_key = ?
        """, (identity_key,)).fetchone()

        if row is None:
            return None

        return _get_node(connection, row["id"])


def upsert_network_node(
    identity_key: str,
    *,
    name: str | None = None,
    hostname: str | None = None,
    node_type: str = "unknown",
    manufacturer: str | None = None,
    model: str | None = None,
    status: str = "online",
) -> dict[str, Any]:
    identity_key = _require_string(identity_key, "Identity key")
    node_type = _require_string(node_type, "Node type")
    status = _require_string(status, "Node status")

    name = _validate_optional_string(name, "Name")
    hostname = _validate_optional_string(hostname, "Hostname")
    manufacturer = _validate_optional_string(manufacturer, "Manufacturer")
    model = _validate_optional_string(model, "Model")

    if status not in VALID_NODE_STATUSES:
        raise ValueError("Invalid network node status.")

    node_id = str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO network_nodes (
                id,
                identity_key,
                name,
                hostname,
                node_type,
                manufacturer,
                model,
                status,
                last_seen,
                last_scan_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                CASE WHEN ? = 'online' THEN CURRENT_TIMESTAMP END,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(identity_key)
            DO UPDATE SET
                name = COALESCE(excluded.name, network_nodes.name),
                hostname = COALESCE(
                    excluded.hostname,
                    network_nodes.hostname
                ),
                node_type = CASE
                    WHEN excluded.node_type != 'unknown'
                    THEN excluded.node_type
                    ELSE network_nodes.node_type
                END,
                manufacturer = COALESCE(
                    excluded.manufacturer,
                    network_nodes.manufacturer
                ),
                model = COALESCE(excluded.model, network_nodes.model),
                status = excluded.status,
                last_seen = CASE
                    WHEN excluded.status = 'online'
                    THEN CURRENT_TIMESTAMP
                    ELSE network_nodes.last_seen
                END,
                last_scan_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
        """, (
            node_id,
            identity_key,
            name,
            hostname,
            node_type,
            manufacturer,
            model,
            status,
            status,
        ))

        row = connection.execute("""
            SELECT id
            FROM network_nodes
            WHERE identity_key = ?
        """, (identity_key,)).fetchone()

        result = _get_node(connection, row["id"])

    if result is None:
        raise RuntimeError("Could not retrieve network node.")

    return result


def update_network_node_status(
    node_id: str,
    status: str,
) -> bool:
    node_id = _require_string(node_id, "Node ID")
    status = _require_string(status, "Node status")

    if status not in VALID_NODE_STATUSES:
        raise ValueError("Invalid network node status.")

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE network_nodes
            SET status = ?,
                last_seen = CASE
                    WHEN ? = 'online' THEN CURRENT_TIMESTAMP
                    ELSE last_seen
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, status, node_id))

    return cursor.rowcount > 0


def add_network_address(
    node_id: str,
    ip_address: str,
    *,
    interface_name: str | None = None,
    is_primary: bool = False,
) -> dict[str, Any]:
    node_id = _require_string(node_id, "Node ID")
    interface_name = _validate_optional_string(
        interface_name,
        "Interface name",
    )

    if not isinstance(is_primary, bool):
        raise ValueError("is_primary must be a boolean.")

    if not isinstance(ip_address, str):
        raise ValueError("IP address must be a string.")

    try:
        address = ipaddress.ip_address(ip_address.strip())
    except ValueError as error:
        raise ValueError("Invalid IP address.") from error

    normalized_ip = str(address)
    address_family = "ipv4" if address.version == 4 else "ipv6"
    address_id = str(uuid.uuid4())

    with get_connection() as connection:
        node = connection.execute("""
            SELECT id
            FROM network_nodes
            WHERE id = ?
        """, (node_id,)).fetchone()

        if node is None:
            raise ValueError("Network node not found.")

        if is_primary:
            connection.execute("""
                UPDATE network_addresses
                SET is_primary = 0
                WHERE node_id = ?
            """, (node_id,))

        connection.execute("""
            INSERT INTO network_addresses (
                id,
                node_id,
                ip_address,
                address_family,
                interface_name,
                is_primary
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id, ip_address)
            DO UPDATE SET
                interface_name = COALESCE(
                    excluded.interface_name,
                    network_addresses.interface_name
                ),
                is_primary = excluded.is_primary,
                last_seen = CURRENT_TIMESTAMP
        """, (
            address_id,
            node_id,
            normalized_ip,
            address_family,
            interface_name,
            int(is_primary),
        ))

        row = connection.execute("""
            SELECT *
            FROM network_addresses
            WHERE node_id = ? AND ip_address = ?
        """, (node_id, normalized_ip)).fetchone()

    return dict(row)


def remove_network_address(
    node_id: str,
    ip_address: str,
) -> bool:
    node_id = _require_string(node_id, "Node ID")

    if not isinstance(ip_address, str):
        raise ValueError("IP address must be a string.")

    try:
        normalized_ip = str(ipaddress.ip_address(ip_address.strip()))
    except ValueError as error:
        raise ValueError("Invalid IP address.") from error

    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM network_addresses
            WHERE node_id = ? AND ip_address = ?
        """, (node_id, normalized_ip))

    return cursor.rowcount > 0


def link_network_nodes(
    source_node_id: str,
    target_node_id: str,
    *,
    connection_type: str = "unknown",
    discovery_source: str | None = None,
) -> str:
    source_node_id = _require_string(source_node_id, "Source node ID")
    target_node_id = _require_string(target_node_id, "Target node ID")
    connection_type = _require_string(
        connection_type,
        "Connection type",
    )
    discovery_source = _validate_optional_string(
        discovery_source,
        "Discovery source",
    )

    if source_node_id == target_node_id:
        raise ValueError("A network node cannot connect to itself.")

    # Недиректированная связь:
    # порядок узлов всегда одинаковый независимо от порядка аргументов.
    source_node_id, target_node_id = sorted((
        source_node_id,
        target_node_id,
    ))

    connection_id = str(uuid.uuid4())

    with get_connection() as connection:
        for node_id in (source_node_id, target_node_id):
            exists = connection.execute("""
                SELECT id
                FROM network_nodes
                WHERE id = ?
            """, (node_id,)).fetchone()

            if exists is None:
                raise ValueError(f"Network node not found: {node_id}")

        connection.execute("""
            INSERT INTO network_connections (
                id,
                source_node_id,
                target_node_id,
                connection_type,
                discovery_source
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(
                source_node_id,
                target_node_id,
                connection_type
            )
            DO UPDATE SET
                discovery_source = COALESCE(
                    excluded.discovery_source,
                    network_connections.discovery_source
                ),
                last_seen = CURRENT_TIMESTAMP
        """, (
            connection_id,
            source_node_id,
            target_node_id,
            connection_type,
            discovery_source,
        ))

        row = connection.execute("""
            SELECT id
            FROM network_connections
            WHERE source_node_id = ?
                AND target_node_id = ?
                AND connection_type = ?
        """, (
            source_node_id,
            target_node_id,
            connection_type,
        )).fetchone()

    return row["id"]


def get_network_connections() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT
                nc.*,
                source.name AS source_name,
                target.name AS target_name
            FROM network_connections AS nc
            JOIN network_nodes AS source
                ON source.id = nc.source_node_id
            JOIN network_nodes AS target
                ON target.id = nc.target_node_id
            ORDER BY nc.first_seen
        """).fetchall()

    return [dict(row) for row in rows]


def link_network_node_to_device(
    node_id: str,
    device_id: str | None,
) -> bool:
    node_id = _require_string(node_id, "Node ID")

    if device_id is not None:
        device_id = _require_string(device_id, "Device ID")

    with get_connection() as connection:
        if device_id is not None:
            device = connection.execute("""
                SELECT id
                FROM devices
                WHERE id = ?
            """, (device_id,)).fetchone()

            if device is None:
                raise ValueError("Device not found.")

        cursor = connection.execute("""
            UPDATE network_nodes
            SET device_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (device_id, node_id))

    return cursor.rowcount > 0


def create_discovery_run(
    scan_type: str = "manual",
) -> str:
    scan_type = _require_string(scan_type, "Scan type")

    if scan_type not in VALID_SCAN_TYPES:
        raise ValueError("Invalid discovery scan type.")

    run_id = str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO network_discovery_runs (
                id,
                scan_type,
                status
            )
            VALUES (?, ?, 'running')
        """, (run_id, scan_type))

    return run_id


def finish_discovery_run(
    run_id: str,
    *,
    status: str = "completed",
    subnets_scanned: int = 0,
    addresses_scanned: int = 0,
    nodes_found: int = 0,
    error: str | None = None,
) -> bool:
    run_id = _require_string(run_id, "Discovery run ID")
    status = _require_string(status, "Discovery run status")
    error = _validate_optional_string(error, "Error")

    if status not in VALID_RUN_STATUSES:
        raise ValueError("Invalid discovery run status.")

    counters = (subnets_scanned, addresses_scanned, nodes_found)

    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        for value in counters
    ):
        raise ValueError("Discovery counters must be non-negative integers.")

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE network_discovery_runs
            SET status = ?,
                completed_at = CURRENT_TIMESTAMP,
                subnets_scanned = ?,
                addresses_scanned = ?,
                nodes_found = ?,
                error = ?
            WHERE id = ? AND status = 'running'
        """, (
            status,
            subnets_scanned,
            addresses_scanned,
            nodes_found,
            error,
            run_id,
        ))

    return cursor.rowcount > 0


def get_discovery_runs(limit: int = 20) -> list[dict[str, Any]]:
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 100
    ):
        raise ValueError("Limit must be between 1 and 100.")

    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM network_discovery_runs
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]


def get_network_settings() -> dict[str, dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT setting_key, setting_value, value_type
            FROM network_settings
            ORDER BY setting_key
        """).fetchall()

    result = {}

    for row in rows:
        value = row["setting_value"]
        value_type = row["value_type"]

        if value is not None and value_type == "json":
            value = json.loads(value)

        elif value is not None and value_type == "boolean":
            normalized = value.lower()

            if normalized not in ("true", "false", "1", "0", "yes", "no"):
                raise ValueError(
                    f"Invalid boolean value for setting: {row['setting_key']}"
                )

            value = normalized in ("true", "1", "yes")

        elif value is not None and value_type == "integer":
            value = int(value)

        result[row["setting_key"]] = {
            "value": value,
            "type": value_type,
        }

    return result


def set_network_setting(
    setting_key: str,
    value: Any,
    value_type: str = "string",
) -> None:
    setting_key = _require_string(setting_key, "Setting key")
    value_type = _require_string(value_type, "Setting type")

    if value_type not in VALID_SETTING_TYPES:
        raise ValueError("Unsupported network setting type.")

    if value is None:
        encoded_value = None

    elif value_type == "json":
        encoded_value = json.dumps(value, ensure_ascii=False)

    elif value_type == "boolean":
        if isinstance(value, bool):
            encoded_value = "true" if value else "false"
        elif isinstance(value, str):
            normalized = value.strip().lower()

            if normalized not in ("true", "false", "1", "0", "yes", "no"):
                raise ValueError("Setting value must be a boolean.")

            encoded_value = (
                "true"
                if normalized in ("true", "1", "yes")
                else "false"
            )
        else:
            raise ValueError("Setting value must be a boolean.")

    elif value_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Setting value must be an integer.")

        encoded_value = str(value)

    else:
        if not isinstance(value, str):
            raise ValueError("Setting value must be a string.")

        encoded_value = value

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO network_settings (
                setting_key,
                setting_value,
                value_type
            )
            VALUES (?, ?, ?)
            ON CONFLICT(setting_key)
            DO UPDATE SET
                setting_value = excluded.setting_value,
                value_type = excluded.value_type,
                updated_at = CURRENT_TIMESTAMP
        """, (
            setting_key,
            encoded_value,
            value_type,
        ))
