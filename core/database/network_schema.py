
def create_network_tables(connection) -> None:
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS network_nodes (
            id TEXT PRIMARY KEY,
            identity_key TEXT NOT NULL UNIQUE,
            name TEXT,
            hostname TEXT,
            node_type TEXT NOT NULL DEFAULT 'unknown',
            manufacturer TEXT,
            model TEXT,
            device_id TEXT,
            status TEXT NOT NULL DEFAULT 'unknown'
                CHECK (status IN ('online', 'offline', 'unknown')),
            first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT,
            last_scan_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (device_id)
                REFERENCES devices(id)
                ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS network_addresses (
            id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            address_family TEXT NOT NULL
                CHECK (address_family IN ('ipv4', 'ipv6')),
            interface_name TEXT,
            is_primary INTEGER NOT NULL DEFAULT 0
                CHECK (is_primary IN (0, 1)),
            first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (node_id)
                REFERENCES network_nodes(id)
                ON DELETE CASCADE,

            UNIQUE (node_id, ip_address)
        );

        CREATE TABLE IF NOT EXISTS network_connections (
            id TEXT PRIMARY KEY,
            source_node_id TEXT NOT NULL,
            target_node_id TEXT NOT NULL,
            connection_type TEXT NOT NULL DEFAULT 'unknown',
            discovery_source TEXT,
            first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            CHECK (source_node_id != target_node_id),

            FOREIGN KEY (source_node_id)
                REFERENCES network_nodes(id)
                ON DELETE CASCADE,

            FOREIGN KEY (target_node_id)
                REFERENCES network_nodes(id)
                ON DELETE CASCADE,

            UNIQUE (
                source_node_id,
                target_node_id,
                connection_type
            )
        );

        CREATE TABLE IF NOT EXISTS network_discovery_runs (
            id TEXT PRIMARY KEY,
            scan_type TEXT NOT NULL DEFAULT 'manual',
            status TEXT NOT NULL DEFAULT 'running'
                CHECK (status IN (
                    'running',
                    'completed',
                    'failed',
                    'cancelled'
                )),
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            subnets_scanned INTEGER NOT NULL DEFAULT 0,
            addresses_scanned INTEGER NOT NULL DEFAULT 0,
            nodes_found INTEGER NOT NULL DEFAULT 0,
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS network_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT,
            value_type TEXT NOT NULL DEFAULT 'string',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_network_nodes_device
            ON network_nodes(device_id);

        CREATE INDEX IF NOT EXISTS idx_network_nodes_status
            ON network_nodes(status);

        CREATE INDEX IF NOT EXISTS idx_network_nodes_last_seen
            ON network_nodes(last_seen);

        CREATE INDEX IF NOT EXISTS idx_network_addresses_node
            ON network_addresses(node_id);

        CREATE INDEX IF NOT EXISTS idx_network_addresses_ip
            ON network_addresses(ip_address);

        CREATE INDEX IF NOT EXISTS idx_network_connections_source
            ON network_connections(source_node_id);

        CREATE INDEX IF NOT EXISTS idx_network_connections_target
            ON network_connections(target_node_id);

        CREATE UNIQUE INDEX IF NOT EXISTS
            idx_network_connections_undirected
        ON network_connections (
            MIN(source_node_id, target_node_id),
            MAX(source_node_id, target_node_id),
            connection_type
        );

        CREATE INDEX IF NOT EXISTS idx_network_discovery_started
            ON network_discovery_runs(started_at);
    """)

    connection.executemany("""
        INSERT OR IGNORE INTO network_settings (
            setting_key,
            setting_value,
            value_type
        )
        VALUES (?, ?, ?)
    """, [
        ("automatic_monitoring", "false", "boolean"),
        ("scan_interval_seconds", "300", "integer"),
    ])
