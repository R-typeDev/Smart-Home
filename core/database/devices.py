
import json
import uuid
from typing import Any

from database.connection import get_connection


DEVICE_FIELDS = {
    "name",
    "category",
    "type",
    "manufacturer",
    "model",
    "barcode",
    "serial_number",
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
            ds.source_id,
            ds.device_id,
            ds.source_type,
            ds.handler_id,
            ds.integration_id,
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
            i.name AS integration_name,
            i.integration_type,
            i.enabled AS integration_enabled
        FROM device_sources AS ds
        LEFT JOIN integration_instances AS ii
            ON ii.id = ds.instance_id
        LEFT JOIN integrations AS i
            ON i.id = ds.integration_id
        WHERE ds.device_id = ?
        ORDER BY ds.priority, ds.source_type, ds.handler_id
    """, (device_id,)).fetchall()

    return [dict(row) for row in rows]


def _get_images(connection, device_id: str) -> list[dict[str, Any]]:
    rows = connection.execute("""
        SELECT
            di.image_id,
            di.asset_key,
            di.filename,
            di.original_filename,
            di.image_source,
            di.image_type,
            di.mime_type,
            di.source_url,
            dia.image_role,
            di.created_at,
            di.updated_at
        FROM device_image_assignments AS dia
        JOIN device_images AS di
            ON di.image_id = dia.image_id
        WHERE dia.device_id = ?
        ORDER BY
            CASE dia.image_role
                WHEN 'primary' THEN 0
                ELSE 1
            END,
            dia.created_at
    """, (device_id,)).fetchall()

    return [dict(row) for row in rows]


def get_device_images(device_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        return _get_images(connection, device_id)


def get_devices() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM devices
            ORDER BY name COLLATE NOCASE
        """).fetchall()

        devices = [dict(row) for row in rows]

        for device in devices:
            device["sources"] = _get_sources(
                connection,
                device["id"],
            )
            device["images"] = _get_images(
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
        device["images"] = _get_images(connection, device_id)

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
    category: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    serial_number: str | None = None,
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
                category,
                type,
                manufacturer,
                model,
                barcode,
                serial_number,
                room_id,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_device_id,
            display_code,
            name.strip(),
            category,
            device_type.strip(),
            manufacturer,
            model,
            barcode,
            serial_number,
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
) -> str:
    if not isinstance(external_id, str) or not external_id.strip():
        raise ValueError("External device ID is required.")

    external_id = external_id.strip()

    with get_connection() as connection:
        instance = connection.execute("""
            SELECT integration_id
            FROM integration_instances
            WHERE id = ?
        """, (instance_id,)).fetchone()

        if instance is None:
            raise ValueError("Integration instance not found.")

        existing = connection.execute("""
            SELECT source_id, device_id
            FROM device_sources
            WHERE instance_id = ? AND external_id = ?
        """, (instance_id, external_id)).fetchone()

        if existing is not None:
            if existing["device_id"] != device_id:
                raise ValueError(
                    "This external device is already linked "
                    "to another Smart Home device."
                )

            return existing["source_id"]

        source_id = str(uuid.uuid4())

        connection.execute("""
            INSERT INTO device_sources (
                source_id,
                device_id,
                source_type,
                handler_id,
                integration_id,
                instance_id,
                external_id,
                source_name,
                enabled,
                priority
            )
            VALUES (?, ?, 'integration', ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            device_id,
            instance["integration_id"],
            instance["integration_id"],
            instance_id,
            external_id,
            source_name,
            int(enabled),
            priority,
        ))

    return source_id


def add_core_device_source(
    device_id: str,
    handler_id: str,
    external_id: str,
    source_name: str | None = None,
    enabled: bool = True,
    priority: int = 100,
) -> str:
    if not isinstance(handler_id, str) or not handler_id.strip():
        raise ValueError("Core handler ID is required.")

    if not isinstance(external_id, str) or not external_id.strip():
        raise ValueError("External device ID is required.")

    handler_id = handler_id.strip()
    external_id = external_id.strip()

    with get_connection() as connection:
        existing = connection.execute("""
            SELECT source_id
            FROM device_sources
            WHERE device_id = ?
                AND source_type = 'core'
                AND handler_id = ?
                AND external_id = ?
        """, (
            device_id,
            handler_id,
            external_id,
        )).fetchone()

        if existing is not None:
            return existing["source_id"]

        source_id = str(uuid.uuid4())

        connection.execute("""
            INSERT INTO device_sources (
                source_id,
                device_id,
                source_type,
                handler_id,
                external_id,
                source_name,
                enabled,
                priority
            )
            VALUES (?, ?, 'core', ?, ?, ?, ?, ?)
        """, (
            source_id,
            device_id,
            handler_id,
            external_id,
            source_name,
            int(enabled),
            priority,
        ))

    return source_id


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


def update_device_source_by_id(
    source_id: str,
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
    values.append(source_id)

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE device_sources
            SET {assignments},
                updated_at = CURRENT_TIMESTAMP
            WHERE source_id = ?
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


def remove_device_source_by_id(source_id: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM device_sources
            WHERE source_id = ?
        """, (source_id,))

    return cursor.rowcount > 0


def set_device_source_secret(
    device_id: str,
    instance_id: str,
    secret_key: str,
    encrypted_value: bytes,
) -> None:
    with get_connection() as connection:
        row = connection.execute("""
            SELECT source_id
            FROM device_sources
            WHERE device_id = ? AND instance_id = ?
        """, (device_id, instance_id)).fetchone()

        if row is None:
            raise ValueError("Device source not found.")

        connection.execute("""
            INSERT INTO device_source_secrets (
                source_id,
                secret_key,
                encrypted_value
            )
            VALUES (?, ?, ?)
            ON CONFLICT(source_id, secret_key)
            DO UPDATE SET
                encrypted_value = excluded.encrypted_value,
                updated_at = CURRENT_TIMESTAMP
        """, (
            row["source_id"],
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
            SELECT dss.encrypted_value
            FROM device_source_secrets AS dss
            JOIN device_sources AS ds
                ON ds.source_id = dss.source_id
            WHERE ds.device_id = ?
                AND ds.instance_id = ?
                AND dss.secret_key = ?
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
            WHERE source_id = (
                SELECT source_id
                FROM device_sources
                WHERE device_id = ? AND instance_id = ?
            )
            AND secret_key = ?
        """, (
            device_id,
            instance_id,
            secret_key,
        ))

    return cursor.rowcount > 0


def set_device_image(
    device_id: str,
    *,
    asset_key: str,
    filename: str,
    image_source: str,
    image_type: str = "model",
    original_filename: str | None = None,
    mime_type: str | None = None,
    source_url: str | None = None,
    image_role: str = "primary",
) -> str:
    if not asset_key or not asset_key.strip():
        raise ValueError("Image asset key is required.")

    if not filename or not filename.strip():
        raise ValueError("Image filename is required.")

    if not image_source or not image_source.strip():
        raise ValueError("Image source is required.")

    with get_connection() as connection:
        device = connection.execute(
            "SELECT id FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()

        if device is None:
            raise ValueError("Device not found.")

        existing = connection.execute("""
            SELECT image_id
            FROM device_images
            WHERE asset_key = ?
        """, (asset_key.strip(),)).fetchone()

        if existing:
            image_id = existing["image_id"]

            connection.execute("""
                UPDATE device_images
                SET filename = ?,
                    original_filename = ?,
                    image_source = ?,
                    image_type = ?,
                    mime_type = ?,
                    source_url = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE image_id = ?
            """, (
                filename.strip(),
                original_filename,
                image_source.strip(),
                image_type,
                mime_type,
                source_url,
                image_id,
            ))
        else:
            image_id = str(uuid.uuid4())

            connection.execute("""
                INSERT INTO device_images (
                    image_id,
                    asset_key,
                    filename,
                    original_filename,
                    image_source,
                    image_type,
                    mime_type,
                    source_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                image_id,
                asset_key.strip(),
                filename.strip(),
                original_filename,
                image_source.strip(),
                image_type,
                mime_type,
                source_url,
            ))

        connection.execute("""
            INSERT INTO device_image_assignments (
                device_id,
                image_id,
                image_role
            )
            VALUES (?, ?, ?)
            ON CONFLICT(device_id, image_id, image_role)
            DO NOTHING
        """, (
            device_id,
            image_id,
            image_role,
        ))

    return image_id


def remove_device_image(
    device_id: str,
    image_id: str,
    image_role: str | None = None,
) -> bool:
    with get_connection() as connection:
        if image_role is None:
            cursor = connection.execute("""
                DELETE FROM device_image_assignments
                WHERE device_id = ? AND image_id = ?
            """, (device_id, image_id))
        else:
            cursor = connection.execute("""
                DELETE FROM device_image_assignments
                WHERE device_id = ?
                    AND image_id = ?
                    AND image_role = ?
            """, (device_id, image_id, image_role))

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
