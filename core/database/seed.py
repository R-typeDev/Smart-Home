from database.connection import get_connection


INITIAL_INTEGRATIONS = [
    {
        "id": "tplink_router",
        "name": "TP-Link Router",
        "integration_type": "tplink_router",
    },
    {
        "id": "tuya_local",
        "name": "Tuya Local",
        "integration_type": "tuya_local",
    },
]


def seed_integrations() -> None:
    with get_connection() as connection:
        for integration in INITIAL_INTEGRATIONS:
            connection.execute(
                """
                INSERT INTO integrations (
                    id,
                    name,
                    integration_type
                )
                VALUES (
                    :id,
                    :name,
                    :integration_type
                )
                ON CONFLICT(id) DO NOTHING
                """,
                integration,
            )