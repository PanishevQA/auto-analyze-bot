from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

MIGRATION_VERSION = 2
P1_COLUMNS = {
    "analysis_request_id": "VARCHAR(64)", "idempotency_key": "VARCHAR(128)",
    "status": "VARCHAR(20) NOT NULL DEFAULT 'COMPLETED'", "source_url": "TEXT",
    "source_mode": "VARCHAR(20) NOT NULL DEFAULT 'MANUAL'",
    "photos_metadata": "TEXT NOT NULL DEFAULT '[]'", "condition_data": "TEXT NOT NULL DEFAULT '{}'",
    "market_status": "VARCHAR(20) NOT NULL DEFAULT 'UNAVAILABLE'",
    "vision_status": "VARCHAR(20) NOT NULL DEFAULT 'UNAVAILABLE'", "model_uri": "TEXT",
    "prompt_version": "VARCHAR(100)", "adapter_version": "VARCHAR(100)",
    "catalog_version": "VARCHAR(100)", "formula_version": "VARCHAR(100)",
    "parent_calculation_id": "INTEGER REFERENCES calculations(id)",
    "updated_at": "TIMESTAMP",
    "test_mode": "BOOLEAN", "parts_data": "TEXT", "parts_status": "VARCHAR(20)",
    "parts_quoted_at": "TIMESTAMP", "parts_provider": "VARCHAR(100)",
}

async def migrate(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        rows = await connection.execute(text("PRAGMA table_info(calculations)"))
        existing = {row[1] for row in rows}
        if not existing: return
        for name, definition in P1_COLUMNS.items():
            if name not in existing:
                await connection.execute(text(f'ALTER TABLE calculations ADD COLUMN "{name}" {definition}'))
        await connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS calculations_idempotency_idx ON calculations(idempotency_key)"))
        await connection.execute(text(f"PRAGMA user_version = {MIGRATION_VERSION}"))
