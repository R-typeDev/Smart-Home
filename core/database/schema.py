
from database.connection import get_connection
from database.seed import seed_integrations


SCHEMA_VERSION = "2"


def create_schema(connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS schema_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS integrations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            integration_type TEXT NOT NULL,
            description TEXT,
            version TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS integration_instances (
            id TEXT PRIMARY KEY,
            integration_id TEXT NOT NULL,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (integration_id)
                REFERENCES integrations(id)
                ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS integration_settings (
            instance_id TEXT NOT NULL,
            setting_key TEXT NOT NULL,
            setting_value TEXT,
            value_type TEXT NOT NULL DEFAULT 'string',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (instance_id, setting_key),
            FOREIGN KEY (instance_id)
                REFERENCES integration_instances(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS secrets (
            instance_id TEXT NOT NULL,
            secret_key TEXT NOT NULL,
            encrypted_value BLOB NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (instance_id, secret_key),
            FOREIGN KEY (instance_id)
                REFERENCES integration_instances(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            display_code TEXT UNIQUE,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            manufacturer TEXT,
            model TEXT,
            room_id TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id)
                REFERENCES rooms(id)
                ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS device_sources (
            device_id TEXT NOT NULL,
            instance_id TEXT NOT NULL,
            external_id TEXT NOT NULL,
            source_name TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),
            priority INTEGER NOT NULL DEFAULT 100,
            last_seen TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (device_id, instance_id),
            UNIQUE (instance_id, external_id),
            FOREIGN KEY (device_id)
                REFERENCES devices(id)
                ON DELETE CASCADE,
            FOREIGN KEY (instance_id)
                REFERENCES integration_instances(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS device_source_secrets (
            device_id TEXT NOT NULL,
            instance_id TEXT NOT NULL,
            secret_key TEXT NOT NULL,
            encrypted_value BLOB NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (device_id, instance_id, secret_key),
            FOREIGN KEY (device_id, instance_id)
                REFERENCES device_sources(device_id, instance_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS device_properties (
            device_id TEXT NOT NULL,
            property_key TEXT NOT NULL,
            property_value TEXT,
            value_type TEXT NOT NULL DEFAULT 'string',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (device_id, property_key),
            FOREIGN KEY (device_id)
                REFERENCES devices(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS device_features (
            device_id TEXT NOT NULL,
            feature_key TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            feature_type TEXT NOT NULL,
            description TEXT,
            config_json TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (device_id, feature_key),
            FOREIGN KEY (device_id)
                REFERENCES devices(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS device_states (
            device_id TEXT NOT NULL,
            state_key TEXT NOT NULL,
            state_value TEXT,
            value_type TEXT NOT NULL DEFAULT 'string',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (device_id, state_key),
            FOREIGN KEY (device_id)
                REFERENCES devices(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_instances_integration
            ON integration_instances(integration_id);

        CREATE INDEX IF NOT EXISTS idx_devices_room
            ON devices(room_id);

        CREATE INDEX IF NOT EXISTS idx_devices_type
            ON devices(type);

        CREATE INDEX IF NOT EXISTS idx_device_sources_instance
            ON device_sources(instance_id);

        CREATE INDEX IF NOT EXISTS idx_device_sources_priority
            ON device_sources(device_id, enabled, priority);

        CREATE INDEX IF NOT EXISTS idx_device_properties_device
            ON device_properties(device_id);

        CREATE INDEX IF NOT EXISTS idx_device_features_device
            ON device_features(device_id);

        CREATE INDEX IF NOT EXISTS idx_device_states_device
            ON device_states(device_id);

        INSERT INTO schema_metadata (key, value)
        VALUES ('version', '2')
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value;
    """)


def initialize_database() -> None:
    with get_connection() as connection:
        create_schema(connection)

    seed_integrations()
