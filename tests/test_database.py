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


@pytest.mark.asyncio
async def test_idempotency_reservation_is_single_flight(database: Database):
    await database.upsert_user(100)
    first_id, first_created = await database.reserve_analysis(100, "key", "request", {"make": "Lada"})
    second_id, second_created = await database.reserve_analysis(100, "key", "request", {"make": "Lada"})
    assert first_created is True and second_created is False and first_id == second_id

@pytest.mark.asyncio
async def test_parts_condition_and_versions_roundtrip(database: Database):
    await database.upsert_user(100)
    parent=await _save(database,100,1)
    calculation_id=await database.save_calculation(100,car_data={"make":"Ford"},market_data={},
        repair_estimate={},scores={},final_report="x",metadata={"condition_data":{"coverage":"FULL"},
        "parts_data":[{"status":"READY"}],"parts_status":"READY","parts_provider":"official-test",
        "test_mode":True,"parent_calculation_id":parent,"formula_version":"v1"})
    saved=await database.get_calculation_by_id(calculation_id,100)
    assert saved["condition_data"]=={"coverage":"FULL"}
    assert saved["parts_data"]==[{"status":"READY"}] and saved["test_mode"] is True
    assert saved["parent_calculation_id"]==parent and saved["versions"]["formula_version"]=="v1"

@pytest.mark.asyncio
async def test_user_region_update_and_explicit_cleanup(database: Database):
    await database.set_region(300,"Москва")
    assert (await database.get_user(300)).region=="Москва"
    await database.set_region(300,"Казань")
    user=await database.get_user(300); assert user.region=="Казань"
    for index in range(7): await _save(database,300,index)
    await database.cleanup_old_calculations(user.id)
    assert len(await database.get_user_calculations_list(300,99))==5

@pytest.mark.asyncio
async def test_user_preferences_are_persisted(database: Database):
    await database.upsert_user(400)
    await database.set_user_preferences(400,target_profit_rub=75000,parts_condition="USED")
    user=await database.get_user(400)
    assert user.target_profit_rub==75000 and user.parts_condition=="USED"
