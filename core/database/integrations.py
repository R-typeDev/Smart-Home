
import sqlite3
import uuid
from typing import Any

from database.connection import get_connection


def get_integrations() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT *
            FROM integrations
            ORDER BY name COLLATE NOCASE
        """).fetchall()

    return [dict(row) for row in rows]


def get_integration(integration_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute("""
            SELECT *
            FROM integrations
            WHERE id = ?
        """, (integration_id,)).fetchone()

    return dict(row) if row else None


def add_integration(
    integration_id: str,
    name: str,
    integration_type: str,
    description: str | None = None,
    version: str | None = None,
) -> bool:
    if not all(
        isinstance(value, str) and value.strip()
        for value in (integration_id, name, integration_type)
    ):
        return False

    try:
        with get_connection() as connection:
            connection.execute("""
                INSERT INTO integrations (
                    id, name, integration_type, description, version
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                integration_id.strip(),
                name.strip(),
                integration_type.strip(),
                description,
                version,
            ))

        return True

    except sqlite3.IntegrityError:
        return False


def update_integration(
    integration_id: str,
    name: str,
    integration_type: str,
    description: str | None = None,
    version: str | None = None,
) -> bool:
    if not all(
        isinstance(value, str) and value.strip()
        for value in (name, integration_type)
    ):
        return False

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE integrations
            SET name = ?,
                integration_type = ?,
                description = ?,
                version = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            name.strip(),
            integration_type.strip(),
            description,
            version,
            integration_id,
        ))

    return cursor.rowcount > 0


def set_integration_enabled(
    integration_id: str,
    enabled: bool,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE integrations
            SET enabled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (int(enabled), integration_id))

    return cursor.rowcount > 0


def delete_integration(integration_id: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM integrations
            WHERE id = ?
        """, (integration_id,))

    return cursor.rowcount > 0


def get_integration_instances(
    integration_id: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            ii.*,
            i.name AS integration_name,
            i.integration_type
        FROM integration_instances AS ii
        JOIN integrations AS i ON i.id = ii.integration_id
    """

    parameters: tuple[Any, ...] = ()

    if integration_id is not None:
        query += " WHERE ii.integration_id = ?"
        parameters = (integration_id,)

    query += " ORDER BY i.name, ii.name"

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [dict(row) for row in rows]


def get_integration_instance(
    instance_id: str,
) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute("""
            SELECT
                ii.*,
                i.name AS integration_name,
                i.integration_type
            FROM integration_instances AS ii
            JOIN integrations AS i ON i.id = ii.integration_id
            WHERE ii.id = ?
        """, (instance_id,)).fetchone()

    return dict(row) if row else None


def add_integration_instance(
    integration_id: str,
    name: str,
    instance_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Connection name is required.")

    new_id = instance_id or str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute("""
            INSERT INTO integration_instances (
                id, integration_id, name
            )
            VALUES (?, ?, ?)
        """, (
            new_id,
            integration_id,
            name.strip(),
        ))

    instance = get_integration_instance(new_id)

    if instance is None:
        raise RuntimeError("Could not retrieve integration connection.")

    return instance


def update_integration_instance(
    instance_id: str,
    name: str,
) -> bool:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Connection name is required.")

    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE integration_instances
            SET name = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (name.strip(), instance_id))

    return cursor.rowcount > 0


def set_integration_instance_enabled(
    instance_id: str,
    enabled: bool,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            UPDATE integration_instances
            SET enabled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (int(enabled), instance_id))

    return cursor.rowcount > 0


def delete_integration_instance(instance_id: str) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM integration_instances
            WHERE id = ?
        """, (instance_id,))

    return cursor.rowcount > 0


def get_integration_settings(
    instance_id: str,
) -> dict[str, dict[str, str | None]]:
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT setting_key, setting_value, value_type
            FROM integration_settings
            WHERE instance_id = ?
        """, (instance_id,)).fetchall()

    return {
        row["setting_key"]: {
            "value": row["setting_value"],
            "type": row["value_type"],
        }
        for row in rows
    }


def set_integration_setting(
    instance_id: str,
    setting_key: str,
    setting_value: str | None,
    value_type: str = "string",
) -> None:
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO integration_settings (
                instance_id, setting_key, setting_value, value_type
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(instance_id, setting_key)
            DO UPDATE SET
                setting_value = excluded.setting_value,
                value_type = excluded.value_type,
                updated_at = CURRENT_TIMESTAMP
        """, (
            instance_id,
            setting_key,
            setting_value,
            value_type,
        ))


def delete_integration_setting(
    instance_id: str,
    setting_key: str,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM integration_settings
            WHERE instance_id = ? AND setting_key = ?
        """, (instance_id, setting_key))

    return cursor.rowcount > 0


def set_integration_secret(
    instance_id: str,
    secret_key: str,
    encrypted_value: bytes,
) -> None:
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO secrets (
                instance_id, secret_key, encrypted_value
            )
            VALUES (?, ?, ?)
            ON CONFLICT(instance_id, secret_key)
            DO UPDATE SET
                encrypted_value = excluded.encrypted_value,
                updated_at = CURRENT_TIMESTAMP
        """, (
            instance_id,
            secret_key,
            encrypted_value,
        ))


def get_integration_secret(
    instance_id: str,
    secret_key: str,
) -> bytes | None:
    with get_connection() as connection:
        row = connection.execute("""
            SELECT encrypted_value
            FROM secrets
            WHERE instance_id = ? AND secret_key = ?
        """, (instance_id, secret_key)).fetchone()

    return bytes(row["encrypted_value"]) if row else None


def delete_integration_secret(
    instance_id: str,
    secret_key: str,
) -> bool:
    with get_connection() as connection:
        cursor = connection.execute("""
            DELETE FROM secrets
            WHERE instance_id = ? AND secret_key = ?
        """, (instance_id, secret_key))

    return cursor.rowcount > 0
