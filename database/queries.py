import json
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
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

    async def set_user_preferences(self, telegram_id: int, *, target_profit_rub: int | None = None,
                                   parts_condition: str | None = None) -> None:
        async with self.session_factory() as session:
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            if user is None:
                user = User(telegram_id=telegram_id)
                session.add(user)
            if target_profit_rub is not None:
                user.target_profit_rub = target_profit_rub
            if parts_condition is not None:
                user.parts_condition = parts_condition
            await session.commit()

    async def get_user(self, telegram_id: int) -> User | None:
        async with self.session_factory() as session:
            return await session.scalar(select(User).where(User.telegram_id == telegram_id))

    async def save_calculation(
        self, telegram_id: int, *, car_data: dict[str, Any], market_data: dict[str, Any],
        repair_estimate: dict[str, Any], scores: dict[str, Any], final_report: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        async with self.session_factory() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_id == telegram_id))
            if user_id is None:
                raise RuntimeError("Пользователь не найден")
            meta = metadata or {}
            calculation = Calculation(
                user_id=user_id,
                car_data=json.dumps(car_data, ensure_ascii=False),
                market_data=json.dumps(market_data, ensure_ascii=False),
                repair_estimate=json.dumps(repair_estimate, ensure_ascii=False),
                scores=json.dumps(scores, ensure_ascii=False),
                final_report=final_report,
                analysis_request_id=meta.get("analysis_request_id"), idempotency_key=meta.get("idempotency_key"),
                status=meta.get("status", "COMPLETED"), source_url=meta.get("source_url"),
                source_mode=meta.get("source_mode", "MANUAL"),
                photos_metadata=json.dumps(meta.get("photos_metadata", []), ensure_ascii=False),
                condition_data=json.dumps(meta.get("condition_data", {}), ensure_ascii=False),
                market_status=meta.get("market_status", "UNAVAILABLE"),
                vision_status=meta.get("vision_status", "UNAVAILABLE"), model_uri=meta.get("model_uri"),
                prompt_version=meta.get("prompt_version"), adapter_version=meta.get("adapter_version"),
                catalog_version=meta.get("catalog_version"), formula_version=meta.get("formula_version"),
                parent_calculation_id=meta.get("parent_calculation_id"),
                test_mode=meta.get("test_mode"), parts_data=json.dumps(meta.get("parts_data"), ensure_ascii=False),
                parts_status=meta.get("parts_status"), parts_quoted_at=meta.get("parts_quoted_at"),
                parts_provider=meta.get("parts_provider"),
                parts_search_mode=meta.get("parts_search_mode"),parts_source=meta.get("parts_source"),
                parts_complete=meta.get("parts_complete"),
                parts_query_data=json.dumps(meta.get("parts_query_data"),ensure_ascii=False),
                parts_permission_confirmed=meta.get("parts_permission_confirmed"),
                parts_prompt_version=meta.get("parts_prompt_version"),
            )
            session.add(calculation)
            await session.flush()
            calculation_id = calculation.id
            await self._cleanup_old_calculations(session, user_id)
            await session.commit()
            return calculation_id

    async def get_by_idempotency_key(self, key: str, telegram_id: int) -> dict[str, Any] | None:
        async with self.session_factory() as session:
            record = await session.scalar(select(Calculation).join(User).where(
                Calculation.idempotency_key == key, User.telegram_id == telegram_id))
            return self._calculation_dict(record) if record else None

    async def reserve_analysis(self, telegram_id: int, key: str, request_id: str,
                               car_data: dict[str, Any]) -> tuple[int, bool]:
        async with self.session_factory() as session:
            user_id = await session.scalar(select(User.id).where(User.telegram_id == telegram_id))
            if user_id is None: raise RuntimeError("Пользователь не найден")
            existing = await session.scalar(select(Calculation).where(Calculation.idempotency_key == key))
            if existing: return existing.id, False
            record = Calculation(user_id=user_id, car_data=json.dumps(car_data, ensure_ascii=False),
                market_data="{}", repair_estimate="{}", scores="{}", final_report="",
                analysis_request_id=request_id, idempotency_key=key, status="PROCESSING")
            session.add(record)
            try: await session.commit()
            except IntegrityError:
                await session.rollback(); existing = await session.scalar(select(Calculation).where(Calculation.idempotency_key == key))
                return existing.id, False
            return record.id, True

    async def complete_analysis(self, calculation_id: int, **values: Any) -> None:
        serialized = {key: json.dumps(value, ensure_ascii=False) for key, value in values.items()
                      if key in {"car_data", "market_data", "repair_estimate", "scores",
                                 "photos_metadata", "condition_data", "parts_data", "parts_query_data"}}
        serialized.update({key: value for key, value in values.items() if key not in serialized})
        async with self.session_factory() as session:
            await session.execute(update(Calculation).where(Calculation.id == calculation_id).values(**serialized))
            user_id = await session.scalar(select(Calculation.user_id).where(Calculation.id == calculation_id))
            if user_id is not None:
                await self._cleanup_old_calculations(session, user_id)
            await session.commit()

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
        car_model = car.get("car_model") or " ".join(
            part for part in (str(car.get("make", "")), str(car.get("model", ""))) if part
        ) or "Автомобиль"
        return {"id": record.id, "car_model": car_model,
                "year": car.get("year", "—"),
                "mileage": car.get("mileage", car.get("mileage_km", 0)) or 0,
                "created_at": record.created_at, "status": record.status,
                "condition_data": json.loads(record.condition_data or "{}"),
                "photos_metadata": json.loads(record.photos_metadata or "[]"),
                "parent_calculation_id": record.parent_calculation_id}

    @staticmethod
    def _calculation_dict(record: Calculation) -> dict[str, Any]:
        return {"id": record.id, "user_id": record.user_id, "car_data": json.loads(record.car_data),
                "market_data": json.loads(record.market_data),
                "repair_estimate": json.loads(record.repair_estimate),
                "scores": json.loads(record.scores), "final_report": record.final_report,
                "condition_data": json.loads(record.condition_data or "{}"),
                "parts_data": json.loads(record.parts_data) if record.parts_data else None,
                "parts_status": record.parts_status, "parts_quoted_at": record.parts_quoted_at,
                "parts_provider": record.parts_provider, "test_mode": record.test_mode,
                "parts_search_mode":record.parts_search_mode,"parts_source":record.parts_source,
                "parts_complete":record.parts_complete,
                "parts_query_data":json.loads(record.parts_query_data) if record.parts_query_data else None,
                "parts_permission_confirmed":record.parts_permission_confirmed,
                "parts_prompt_version":record.parts_prompt_version,
                "vision_status": record.vision_status, "market_status": record.market_status,
                "versions": {"model_uri": record.model_uri, "prompt_version": record.prompt_version,
                    "adapter_version": record.adapter_version, "catalog_version": record.catalog_version,
                    "formula_version": record.formula_version},
                "parent_calculation_id": record.parent_calculation_id,
                "created_at": record.created_at, "updated_at": record.updated_at}
