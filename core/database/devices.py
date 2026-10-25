
import uuid

from database.connection import get_connection


def _resolve_instance_id(
    integration_id: str,
    integration_instance_id: str | None = None,
) -> str | None:
    if integration_instance_id:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM integration_instances
                WHERE id = ? AND integration_id = ?
                """,
                (integration_instance_id, integration_id),
            ).fetchone()

        if row is None:
            raise ValueError(
                "Integration instance does not match the integration."
            )

        return row["id"]

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id
            FROM integration_instances
            WHERE integration_id = ? AND enabled = 1
            """,
            (integration_id,),
        ).fetchall()

    if len(rows) == 1:
        return rows[0]["id"]

    return None


def get_devices() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                name,
                type,
                manufacturer,
                model,
                integration_id,
                external_id,
                room_id,
                enabled,
                created_at,
                integration_instance_id
            FROM devices
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_device(device_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                name,
                type,
                manufacturer,
                model,
                integration_id,
                external_id,
                room_id,
                enabled,
                created_at,
                integration_instance_id
            FROM devices
            WHERE id = ?
            """,
            (device_id,),
        ).fetchone()

    return dict(row) if row else None


def add_device(
    *,
    name: str,
    device_type: str,
    integration_id: str,
    manufacturer: str | None = None,
    model: str | None = None,
    external_id: str | None = None,
    room_id: str | None = None,
    enabled: bool = True,
    integration_instance_id: str | None = None,
    device_id: str | None = None,
) -> dict:
    resolved_instance_id = _resolve_instance_id(
        integration_id,
        integration_instance_id,
    )

    new_device_id = device_id or str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO devices (
                id,
                name,
                type,
                manufacturer,
                model,
                integration_id,
                external_id,
                room_id,
                enabled,
                integration_instance_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_device_id,
                name,
                device_type,
                manufacturer,
                model,
                integration_id,
                external_id,
                room_id,
                int(enabled),
                resolved_instance_id,
            ),
        )

    device = get_device(new_device_id)

    if device is None:
        raise RuntimeError(
            "The device was inserted but could not be read."
        )

    return device


def update_device(device_id: str, **fields) -> dict | None:
    allowed_fields = {
        "name",
        "type",
        "manufacturer",
        "model",
        "integration_id",
        "external_id",
        "room_id",
        "enabled",
        "integration_instance_id",
    }

    updates = {
        key: value
        for key, value in fields.items()
        if key in allowed_fields
    }

    if not updates:
        return get_device(device_id)

    current = get_device(device_id)

    if current is None:
        return None

    integration_id = updates.get(
        "integration_id",
        current["integration_id"],
    )

    if (
        "integration_id" in updates
        or "integration_instance_id" in updates
    ):
        if "integration_instance_id" in updates:
            requested_instance_id = updates["integration_instance_id"]
        elif "integration_id" in updates:
            requested_instance_id = None
        else:
            requested_instance_id = current["integration_instance_id"]

        updates["integration_instance_id"] = _resolve_instance_id(
            integration_id,
            requested_instance_id,
        )

    if "enabled" in updates:
        updates["enabled"] = int(bool(updates["enabled"]))

    assignments = ", ".join(
        f'"{field}" = ?'
        for field in updates
    )

    values = list(updates.values())
    values.append(device_id)

    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE devices
            SET {assignments}
            WHERE id = ?
            """,
            values,
        )

    return get_device(device_id)


def set_device_enabled(device_id: str, enabled: bool) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE devices
            SET enabled = ?
            WHERE id = ?
            """,
            (int(enabled), device_id),
        )

    return cursor.rowcount > 0


def delete_device(device_id: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM devices WHERE id = ?",
            (device_id,),
        )

    return cursor.rowcount > 0
