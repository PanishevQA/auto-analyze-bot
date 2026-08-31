from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database.models import Base
from database.queries import Database


@pytest.fixture
async def database(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield Database(factory)
    await engine.dispose()


async def _save(database: Database, telegram_id: int, index: int) -> int:
    return await database.save_calculation(
        telegram_id,
        car_data={"car_model": f"Car {index}", "year": 2020, "mileage": index},
        market_data={"quick": 100}, repair_estimate={"repair_items": []},
        scores={"profit": 1}, final_report=f"report {index}",
    )


@pytest.mark.asyncio
async def test_sixth_calculation_removes_oldest(database: Database):
    await database.upsert_user(100)
    ids = [await _save(database, 100, index) for index in range(6)]
    history = await database.get_user_calculations_list(100)
    assert len(history) == 5
    assert ids[0] not in {item["id"] for item in history}
    assert [item["mileage"] for item in history] == [5, 4, 3, 2, 1]


@pytest.mark.asyncio
async def test_history_is_restricted_to_owner(database: Database):
    await database.upsert_user(100)
    await database.upsert_user(200)
    calculation_id = await _save(database, 100, 1)
    assert await database.get_calculation_by_id(calculation_id, 200) is None
    own = await database.get_calculation_by_id(calculation_id, 100)
    assert own is not None and own["final_report"] == "report 1"


@pytest.mark.asyncio
async def test_json_roundtrip_and_user_separation(database: Database):
    await database.upsert_user(100, "Москва и МО")
    await database.upsert_user(200, "Весь РФ")
    first = await _save(database, 100, 1)
    await _save(database, 200, 2)
    details = await database.get_calculation_by_id(first, 100)
    assert details["car_data"]["car_model"] == "Car 1"
    assert len(await database.get_user_calculations_list(100)) == 1
    assert len(await database.get_user_calculations_list(200)) == 1
