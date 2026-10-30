
import json
import uuid
from typing import Any

from database.connection import get_connection


DEVICE_FIELDS = {
    "name",
    "type",
    "manufacturer",
    "model",
    "room_id",
    "display_code",
    "enabled",
}


def _decode_value(value: str | None, value_type: str) -> Any:
    if value is None:
        return None

    if value_type == "json":
        return json.loads(value)

    if value_type == "boolean":
        return value.lower() in ("true", "1", "yes")

    if value_type == "integer":
        return int(value)

    if value_type == "float":
        return float(value)

    return value


def _encode_value(value: Any, value_type: str) -> str | None:
    if value is None:
        return None

    if value_type in ("json", "boolean", "integer", "float"):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def _get_sources(connection, device_id: str) -> list[dict[str, Any]]:
    rows = connection.execute("""
        SELECT
            ds.device_id,
            ds.instance_id,
            ds.external_id,
            ds.source_name,
            ds.enabled,
            ds.priority,
            ds.last_seen,
            ds.created_at,
            ds.updated_at,
            ii.name AS connection_name,
            ii.enabled AS connection_enabled,
            i.id AS integration_id,
            i.name AS integration_name,
            i.integration_type,
            i.enabled AS integration_enabled
        FROM device_sources AS ds
        JOIN integration_instances AS ii
            ON ii.id = ds.instance_id
        JOIN integrations AS i
            ON i.id = ii.integration_id
        WHERE ds.device_id = ?
        ORDER BY ds.priority, i.name, ii.name
    """, (device_id,)).fetchall()

    return [dict(row) for row in rows]


def get_devices() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT
                id,
                display_code,
                name,
                type,
                manufacturer,
                model,
                room_id,
                enabled,
                created_at,
                updated_at
            FROM devices
            ORDER BY name COLLATE NOCASE
        """).fetchall()

        devices = [dict(row) for row in rows]

        for device in devices:
            device["sources"] = _get_sources(
                connection,
                device["id"],
            )

    return devices


def get_device(device_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute("""
            SELECT *
            FROM devices
            WHERE id = ?
        """, (device_id,)).fetchone()

        if row is None:
            return None

        device = dict(row)
        device["sources"] = _get_sources(connection, device_id)

        properties = connection.execute("""
            SELECT property_key, property_value, value_type
            FROM device_properties
            WHERE device_id = ?
        """, (device_id,)).fetchall()

        features = connection.execute("""
            SELECT
                feature_key,
                feature_name,
                feature_type,
                description,
                config_json
            FROM device_features
            WHERE device_id = ?
        """, (device_id,)).fetchall()

        states = connection.execute("""
            SELECT state_key, state_value, value_type, updated_at
            FROM device_states
            WHERE device_id = ?
        """, (device_id,)).fetchall()

        device["properties"] = {
            item["property_key"]: {
                "value": _decode_value(
                    item["property_value"],
                    item["value_type"],
                ),
                "type": item["value_type"],
            }
            for item in properties
        }

        device["features"] = [
            {
                "key": item["feature_key"],
                "name": item["feature_name"],
                "type": item["feature_type"],
                "description": item["description"],
                "config": (
                    json.loads(item["config_json"])
                    if item["config_json"]
                    else None
                ),
            }
            for item in features
        ]

        device["states"] = {
            item["state_key"]: {
                "value": _decode_value(
                    item["state_value"],
                    item["value_type"],
                ),
                "type": item["value_type"],
                "updated_at": item["updated_at"],
            }
            for item in states
        }

    return device


def add_device(
    *,
    name: str,
    device_type: str,
    manufacturer: str | None = None,
    model: str | None = None,
    room_id: str | None = None,
    display_code: str | None = None,
    enabled: bool = True,
    device_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Device name is required.")

    if not isinstance(device_type, str) or not device_type.strip():
        raise ValueError("Device type is required.")

    new_device_id = device_id or str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO devices (
                id,
                display_code,
                name,
                type,
                manufacturer,
                model,
                room_id,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_device_id,
            display_code,
            name.strip(),
            device_type.strip(),
            manufacturer,
            model,
            room_id,
            int(enabled),
        ))

    device = get_device(new_device_id)

    if device is None:
        raise RuntimeError("Could not retrieve the created device.")

    return device


def update_device(
    device_id: str,
    **fields: Any,
) -> dict[str, Any] | None:
    updates = {
        key: value
        for key, value in fields.items()
        if key in DEVICE_FIELDS
    }

    if not updates:
        return get_device(device_id)

    if "enabled" in updates:
        updates["enabled"] = int(bool(updates["enabled"]))

    assignments = ", ".join(
        f'"{field}" = ?'
        for field in updates
    )

    values = list(updates.values())
    values.append(device_id)

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE devices
            SET {assignments},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            values,
        )

        if cursor.rowcount == 0:
            return None

    return get_device(device_id)


def set_device_enabled(device_id: str, enabled: bool) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE devices
            SET enabled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (int(enabled), device_id))

    return cursor.rowcount > 0


def delete_device(device_id: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM devices WHERE id = ?",
            (device_id,),
        )

    return cursor.rowcount > 0


def add_device_source(
    device_id: str,
    instance_id: str,
    external_id: str,
    source_name: str | None = None,
    enabled: bool = True,
    priority: int = 100,
) -> None:
    if not isinstance(external_id, str) or not external_id.strip():
        raise ValueError("External device ID is required.")

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO device_sources (
                device_id,
                instance_id,
                external_id,
                source_name,
                enabled,
                priority
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            device_id,
            instance_id,
            external_id.strip(),
            source_name,
            int(enabled),
            priority,
        ))


def update_device_source(
    device_id: str,
    instance_id: str,
    *,
    source_name: str | None = None,
    enabled: bool | None = None,
    priority: int | None = None,
) -> bool:
    updates = {}

    if source_name is not None:
        updates["source_name"] = source_name

    if enabled is not None:
        updates["enabled"] = int(enabled)

    if priority is not None:
        updates["priority"] = priority

    if not updates:
        return False

    assignments = ", ".join(
        f'"{field}" = ?'
        for field in updates
    )

    values = list(updates.values())
    values.extend((device_id, instance_id))

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE device_sources
            SET {assignments},
                updated_at = CURRENT_TIMESTAMP
            WHERE device_id = ? AND instance_id = ?
            """,
            values,
        )

    return cursor.rowcount > 0


def remove_device_source(
    device_id: str,
    instance_id: str,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM device_sources
            WHERE device_id = ? AND instance_id = ?
        """, (device_id, instance_id))

    return cursor.rowcount > 0


def set_device_source_secret(
    device_id: str,
    instance_id: str,
    secret_key: str,
    encrypted_value: bytes,
) -> None:
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO device_source_secrets (
                device_id,
                instance_id,
                secret_key,
                encrypted_value
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id, instance_id, secret_key)
            DO UPDATE SET
                encrypted_value = excluded.encrypted_value,
                updated_at = CURRENT_TIMESTAMP
        """, (
            device_id,
            instance_id,
            secret_key,
            encrypted_value,
        ))


def get_device_source_secret(
    device_id: str,
    instance_id: str,
    secret_key: str,
) -> bytes | None:
    with get_connection() as connection:
        row = connection.execute("""
            SELECT encrypted_value
            FROM device_source_secrets
            WHERE device_id = ?
                AND instance_id = ?
                AND secret_key = ?
        """, (
            device_id,
            instance_id,
            secret_key,
        )).fetchone()

    return bytes(row["encrypted_value"]) if row else None


def delete_device_source_secret(
    device_id: str,
    instance_id: str,
    secret_key: str,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM device_source_secrets
            WHERE device_id = ?
                AND instance_id = ?
                AND secret_key = ?
        """, (
            device_id,
            instance_id,
            secret_key,
        ))

    return cursor.rowcount > 0


def set_device_property(
    device_id: str,
    property_key: str,
    value: Any,
    value_type: str = "string",
) -> None:
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO device_properties (
                device_id,
                property_key,
                property_value,
                value_type
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id, property_key)
            DO UPDATE SET
                property_value = excluded.property_value,
                value_type = excluded.value_type,
                updated_at = CURRENT_TIMESTAMP
        """, (
            device_id,
            property_key,
            _encode_value(value, value_type),
            value_type,
        ))


def set_device_feature(
    device_id: str,
    feature_key: str,
    feature_name: str,
    feature_type: str,
    description: str | None = None,
    config: dict[str, Any] | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO device_features (
                device_id,
                feature_key,
                feature_name,
                feature_type,
                description,
                config_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, feature_key)
            DO UPDATE SET
                feature_name = excluded.feature_name,
                feature_type = excluded.feature_type,
                description = excluded.description,
                config_json = excluded.config_json,
                updated_at = CURRENT_TIMESTAMP
        """, (
            device_id,
            feature_key,
            feature_name,
            feature_type,
            description,
            json.dumps(config, ensure_ascii=False)
            if config is not None else None,
        ))


def set_device_state(
    device_id: str,
    state_key: str,
    value: Any,
    value_type: str = "string",
) -> None:
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO device_states (
                device_id,
                state_key,
                state_value,
                value_type
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id, state_key)
            DO UPDATE SET
                state_value = excluded.state_value,
                value_type = excluded.value_type,
                updated_at = CURRENT_TIMESTAMP
        """, (
            device_id,
            state_key,
            _encode_value(value, value_type),
            value_type,
        ))
