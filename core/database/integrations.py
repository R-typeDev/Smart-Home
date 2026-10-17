
import sqlite3

from core.database.connection import get_connection


def get_integrations() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                name,
                integration_type,
                enabled,
                created_at
            FROM integrations
            ORDER BY name
            """
        ).fetchall()

        return [dict(row) for row in rows]


def get_integration(integration_id: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                name,
                integration_type,
                enabled,
                created_at
            FROM integrations
            WHERE id = ?
            """,
            (integration_id,),
        ).fetchone()

        return dict(row) if row else None


def set_integration_enabled(
    integration_id: str,
    enabled: bool,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE integrations
            SET enabled = ?
            WHERE id = ?
            """,
            (int(enabled), integration_id),
        )

        return cursor.rowcount > 0


def add_integration(
    integration_id: str,
    name: str,
    integration_type: str,
) -> bool:
    if not all(
        isinstance(value, str) and value.strip()
        for value in (integration_id, name, integration_type)
    ):
        return False

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO integrations (
                    id,
                    name,
                    integration_type
                )
                VALUES (?, ?, ?)
                """,
                (
                    integration_id.strip(),
                    name.strip(),
                    integration_type.strip(),
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def delete_integration(integration_id: str) -> bool:
    with get_connection() as connection:
        linked_devices = connection.execute(
            """
            SELECT COUNT(*)
            FROM devices
            WHERE integration_id = ?
            """,
            (integration_id,),
        ).fetchone()[0]

        if linked_devices > 0:
            return False

        cursor = connection.execute(
            """
            DELETE FROM integrations
            WHERE id = ?
            """,
            (integration_id,),
        )

        return cursor.rowcount > 0


def update_integration(
    integration_id: str,
    name: str,
    integration_type: str,
) -> bool:
    if not all(
        isinstance(value, str) and value.strip()
        for value in (integration_id, name, integration_type)
    ):
        return False

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE integrations
                SET name = ?,
                    integration_type = ?
                WHERE id = ?
                """,
                (
                    name.strip(),
                    integration_type.strip(),
                    integration_id.strip(),
                ),
            )

            return cursor.rowcount > 0

    except sqlite3.IntegrityError:
        return False
