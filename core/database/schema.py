
from database.connection import get_connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS integrations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                integration_type TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS integration_instances (
                id TEXT PRIMARY KEY,
                integration_id TEXT NOT NULL,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (integration_id)
                    REFERENCES integrations(id)
                    ON DELETE RESTRICT
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                manufacturer TEXT,
                model TEXT,
                integration_id TEXT NOT NULL,
                external_id TEXT,
                room_id TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                integration_instance_id TEXT,

                UNIQUE (integration_instance_id, external_id),

                FOREIGN KEY (integration_id)
                    REFERENCES integrations(id)
                    ON DELETE RESTRICT,

                FOREIGN KEY (integration_instance_id)
                    REFERENCES integration_instances(id)
                    ON DELETE SET NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS integration_settings (
                device_id TEXT NOT NULL,
                integration_id TEXT NOT NULL,
                setting_key TEXT NOT NULL,
                setting_value TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE (device_id, setting_key),

                FOREIGN KEY (device_id)
                    REFERENCES devices(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (integration_id)
                    REFERENCES integrations(id)
                    ON DELETE RESTRICT
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_settings_device
            ON integration_settings(device_id)
        """)
