import aiosqlite
from sqlalchemy.ext.asyncio import create_async_engine
from database.migrations import migrate

import pytest

@pytest.mark.asyncio
async def test_migration_preserves_old_rows(tmp_path):
    path=tmp_path/"old.db"
    async with aiosqlite.connect(path) as db:
        await db.execute("CREATE TABLE calculations (id INTEGER PRIMARY KEY, car_data TEXT)")
        await db.execute("INSERT INTO calculations VALUES (1, '{}')"); await db.commit()
    engine=create_async_engine(f"sqlite+aiosqlite:///{path}")
    await migrate(engine); await migrate(engine)
    async with aiosqlite.connect(path) as db:
        columns={row[1] for row in await (await db.execute("PRAGMA table_info(calculations)")).fetchall()}
        count=(await (await db.execute("SELECT COUNT(*) FROM calculations")).fetchone())[0]
        version=(await (await db.execute("PRAGMA user_version")).fetchone())[0]
    await engine.dispose()
    assert {"idempotency_key","condition_data","test_mode","parts_data"} <= columns
    assert count==1 and version==2
