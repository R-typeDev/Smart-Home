
import sqlite3

from core.database.connection import get_connection


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
                created_at
            FROM devices
            ORDER BY name
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
                created_at
            FROM devices
            WHERE id = ?
            """,
            (device_id,),
        ).fetchone()

        return dict(row) if row else None


def add_device(
    device_id: str,
    name: str,
    device_type: str,
    manufacturer: str | None = None,
    model: str | None = None,
    integration_id: str | None = None,
    external_id: str | None = None,
    room_id: str | None = None,
) -> bool:
    if not all(
        isinstance(value, str) and value.strip()
        for value in (device_id, name, device_type)
    ):
        return False

    try:
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
                    room_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id.strip(),
                    name.strip(),
                    device_type.strip(),
                    manufacturer.strip() if isinstance(manufacturer, str) and manufacturer.strip() else None,
                    model.strip() if isinstance(model, str) and model.strip() else None,
                    integration_id.strip() if isinstance(integration_id, str) and integration_id.strip() else None,
                    external_id.strip() if isinstance(external_id, str) and external_id.strip() else None,
                    room_id.strip() if isinstance(room_id, str) and room_id.strip() else None,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def update_device(
    device_id: str,
    name: str,
    device_type: str,
    manufacturer: str | None = None,
    model: str | None = None,
    integration_id: str | None = None,
    external_id: str | None = None,
    room_id: str | None = None,
) -> bool:
    if not all(
        isinstance(value, str) and value.strip()
        for value in (device_id, name, device_type)
    ):
        return False

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE devices
                SET name = ?,
                    type = ?,
                    manufacturer = ?,
                    model = ?,
                    integration_id = ?,
                    external_id = ?,
                    room_id = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    device_type.strip(),
                    manufacturer.strip() if isinstance(manufacturer, str) and manufacturer.strip() else None,
                    model.strip() if isinstance(model, str) and model.strip() else None,
                    integration_id.strip() if isinstance(integration_id, str) and integration_id.strip() else None,
                    external_id.strip() if isinstance(external_id, str) and external_id.strip() else None,
                    room_id.strip() if isinstance(room_id, str) and room_id.strip() else None,
                    device_id.strip(),
                ),
            )

            return cursor.rowcount > 0

    except sqlite3.IntegrityError:
        return False


def set_device_enabled(
    device_id: str,
    enabled: bool,
) -> bool:
    if not isinstance(enabled, bool):
        return False

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
            """
            DELETE FROM devices
            WHERE id = ?
            """,
            (device_id,),
        )

        return cursor.rowcount > 0
