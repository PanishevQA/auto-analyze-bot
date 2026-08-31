import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.models import Calculation, User, async_session


class Database:
    """Изолирует обработчики от SQLAlchemy и всегда фильтрует историю по владельцу."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] = async_session) -> None:
        self.session_factory = session_factory

    async def upsert_user(self, telegram_id: int, region: str = "Весь РФ") -> User:
        async with self.session_factory() as session:
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            if user is None:
                user = User(telegram_id=telegram_id, region=region)
                session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def set_region(self, telegram_id: int, region: str) -> None:
        async with self.session_factory() as session:
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            if user is None:
                user = User(telegram_id=telegram_id, region=region)
                session.add(user)
            else:
                user.region = region
            await session.commit()

    async def get_user(self, telegram_id: int) -> User | None:
        async with self.session_factory() as session:
            return await session.scalar(select(User).where(User.telegram_id == telegram_id))

    async def save_calculation(
        self, telegram_id: int, *, car_data: dict[str, Any], market_data: dict[str, Any],
        repair_estimate: dict[str, Any], scores: dict[str, Any], final_report: str,
    ) -> int:
        async with self.session_factory() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_id == telegram_id))
            if user_id is None:
                raise RuntimeError("Пользователь не найден")
            calculation = Calculation(
                user_id=user_id,
                car_data=json.dumps(car_data, ensure_ascii=False),
                market_data=json.dumps(market_data, ensure_ascii=False),
                repair_estimate=json.dumps(repair_estimate, ensure_ascii=False),
                scores=json.dumps(scores, ensure_ascii=False),
                final_report=final_report,
            )
            session.add(calculation)
            await session.flush()
            calculation_id = calculation.id
            await self._cleanup_old_calculations(session, user_id)
            await session.commit()
            return calculation_id

    async def cleanup_old_calculations(self, user_db_id: int) -> None:
        async with self.session_factory() as session:
            await self._cleanup_old_calculations(session, user_db_id)
            await session.commit()

    async def _cleanup_old_calculations(self, session: AsyncSession, user_db_id: int) -> None:
        keep_ids = select(Calculation.id).where(
            Calculation.user_id == user_db_id
        ).order_by(Calculation.created_at.desc(), Calculation.id.desc()).limit(5)
        await session.execute(
            delete(Calculation).where(
                Calculation.user_id == user_db_id,
                Calculation.id.not_in(keep_ids),
            )
        )

    async def get_user_calculations_list(self, telegram_id: int, limit: int = 5) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 5))
        async with self.session_factory() as session:
            records = (await session.scalars(
                select(Calculation).join(User).where(User.telegram_id == telegram_id)
                .order_by(Calculation.created_at.desc(), Calculation.id.desc()).limit(safe_limit)
            )).all()
            return [self._history_item(record) for record in records]

    async def get_calculation_by_id(self, calc_id: int, telegram_id: int) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            record = await session.scalar(
                select(Calculation).join(User).where(
                    Calculation.id == calc_id, User.telegram_id == telegram_id
                )
            )
            return self._calculation_dict(record) if record else None

    @staticmethod
    def _history_item(record: Calculation) -> dict[str, Any]:
        car = json.loads(record.car_data)
        return {"id": record.id, "car_model": car.get("car_model", "Автомобиль"),
                "year": car.get("year", "—"), "mileage": car.get("mileage", 0),
                "created_at": record.created_at}

    @staticmethod
    def _calculation_dict(record: Calculation) -> dict[str, Any]:
        return {"id": record.id, "car_data": json.loads(record.car_data),
                "market_data": json.loads(record.market_data),
                "repair_estimate": json.loads(record.repair_estimate),
                "scores": json.loads(record.scores), "final_report": record.final_report,
                "created_at": record.created_at}
