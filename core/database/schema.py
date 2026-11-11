
import uuid

from database.connection import get_connection
from database.seed import seed_integrations


SCHEMA_VERSION = "4"


def _create_tables(connection) -> None:
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
            category TEXT,
            type TEXT NOT NULL,
            manufacturer TEXT,
            model TEXT,
            barcode TEXT,
            serial_number TEXT,
            room_id TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id)
                REFERENCES rooms(id)
                ON DELETE SET NULL
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
    """)


def _migrate_devices(connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(devices)"
        ).fetchall()
    }

    migrations = {
        "category": "ALTER TABLE devices ADD COLUMN category TEXT",
        "barcode": "ALTER TABLE devices ADD COLUMN barcode TEXT",
        "serial_number": (
            "ALTER TABLE devices ADD COLUMN serial_number TEXT"
        ),
    }

    for column, statement in migrations.items():
        if column not in columns:
            connection.execute(statement)


def _migrate_device_sources(connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(device_sources)"
        ).fetchall()
    }

    if not columns or "source_id" in columns:
        return

    old_secrets = connection.execute("""
        SELECT device_id, instance_id, secret_key,
               encrypted_value, updated_at
        FROM device_source_secrets
    """).fetchall()

    old_sources = connection.execute("""
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
            ii.integration_id
        FROM device_sources AS ds
        JOIN integration_instances AS ii
            ON ii.id = ds.instance_id
    """).fetchall()

    connection.execute("DROP TABLE device_source_secrets")
    connection.execute("DROP TABLE device_sources")

    _create_device_source_tables(connection)

    source_ids = {}

    for source in old_sources:
        source_id = str(uuid.uuid4())
        source_ids[(source["device_id"], source["instance_id"])] = source_id

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
                priority,
                last_seen,
                created_at,
                updated_at
            )
            VALUES (?, ?, 'integration', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id,
            source["device_id"],
            source["integration_id"],
            source["integration_id"],
            source["instance_id"],
            source["external_id"],
            source["source_name"],
            source["enabled"],
            source["priority"],
            source["last_seen"],
            source["created_at"],
            source["updated_at"],
        ))

    for secret in old_secrets:
        source_id = source_ids.get((
            secret["device_id"],
            secret["instance_id"],
        ))

        if source_id is None:
            continue

        connection.execute("""
            INSERT INTO device_source_secrets (
                source_id,
                secret_key,
                encrypted_value,
                updated_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            source_id,
            secret["secret_key"],
            secret["encrypted_value"],
            secret["updated_at"],
        ))


def _create_device_source_tables(connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS device_sources (
            source_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            source_type TEXT NOT NULL
                CHECK (source_type IN ('core', 'integration')),
            handler_id TEXT NOT NULL,
            integration_id TEXT,
            instance_id TEXT,
            external_id TEXT,
            source_name TEXT,
            enabled INTEGER NOT NULL DEFAULT 1
                CHECK (enabled IN (0, 1)),
            priority INTEGER NOT NULL DEFAULT 100,
            last_seen TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            CHECK (
                (source_type = 'core'
                    AND integration_id IS NULL
                    AND instance_id IS NULL)
                OR
                (source_type = 'integration'
                    AND integration_id IS NOT NULL
                    AND instance_id IS NOT NULL)
            ),

            FOREIGN KEY (device_id)
                REFERENCES devices(id)
                ON DELETE CASCADE,

            FOREIGN KEY (integration_id)
                REFERENCES integrations(id)
                ON DELETE RESTRICT,

            FOREIGN KEY (instance_id)
                REFERENCES integration_instances(id)
                ON DELETE CASCADE,

            UNIQUE (instance_id, external_id)
        );

        CREATE TABLE IF NOT EXISTS device_source_secrets (
            source_id TEXT NOT NULL,
            secret_key TEXT NOT NULL,
            encrypted_value BLOB NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source_id, secret_key),
            FOREIGN KEY (source_id)
                REFERENCES device_sources(source_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_device_sources_device
            ON device_sources(device_id);

        CREATE INDEX IF NOT EXISTS idx_device_sources_instance
            ON device_sources(instance_id);

        CREATE INDEX IF NOT EXISTS idx_device_sources_priority
            ON device_sources(device_id, enabled, priority);

        CREATE INDEX IF NOT EXISTS idx_device_sources_handler
            ON device_sources(handler_id);
    """)


def _create_device_image_tables(connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS device_images (
            image_id TEXT PRIMARY KEY,
            asset_key TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            original_filename TEXT,
            image_source TEXT NOT NULL,
            image_type TEXT NOT NULL,
            mime_type TEXT,
            source_url TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS device_image_assignments (
            device_id TEXT NOT NULL,
            image_id TEXT NOT NULL,
            image_role TEXT NOT NULL DEFAULT 'primary',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            PRIMARY KEY (device_id, image_id, image_role),

            FOREIGN KEY (device_id)
                REFERENCES devices(id)
                ON DELETE CASCADE,

            FOREIGN KEY (image_id)
                REFERENCES device_images(image_id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_device_image_assignments_device
            ON device_image_assignments(device_id);

        CREATE INDEX IF NOT EXISTS idx_device_image_assignments_image
            ON device_image_assignments(image_id);
    """)


def create_schema(connection) -> None:
    _create_tables(connection)

    _migrate_devices(connection)
    _migrate_device_sources(connection)

    _create_device_source_tables(connection)
    _create_device_image_tables(connection)

    connection.executescript("""
        CREATE INDEX IF NOT EXISTS idx_instances_integration
            ON integration_instances(integration_id);

        CREATE INDEX IF NOT EXISTS idx_devices_room
            ON devices(room_id);

        CREATE INDEX IF NOT EXISTS idx_devices_type
            ON devices(type);

        CREATE INDEX IF NOT EXISTS idx_devices_category
            ON devices(category);

        CREATE INDEX IF NOT EXISTS idx_device_properties_device
            ON device_properties(device_id);

        CREATE INDEX IF NOT EXISTS idx_device_features_device
            ON device_features(device_id);

        CREATE INDEX IF NOT EXISTS idx_device_states_device
            ON device_states(device_id);
    """)

    connection.execute("""
        INSERT INTO schema_metadata (key, value)
        VALUES ('version', ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (SCHEMA_VERSION,))


def initialize_database() -> None:
    with get_connection() as connection:
        create_schema(connection)

    seed_integrations()
