from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import asyncpg


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.url)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    def _pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Соединение с БД не открыто")
        return self.pool

    async def init_schema(self) -> None:
        sql = await _read_text(Path(__file__).with_name("schema.sql"))
        await self._pool().execute(sql)

    async def upsert_user(self, telegram_id: int, region: str = "Весь РФ") -> asyncpg.Record:
        return await self._pool().fetchrow(
            """INSERT INTO users (telegram_id, region) VALUES ($1, $2)
               ON CONFLICT (telegram_id) DO UPDATE SET region = EXCLUDED.region
               RETURNING *""",
            telegram_id, region,
        )

    async def set_region(self, telegram_id: int, region: str) -> None:
        await self._pool().execute(
            "UPDATE users SET region=$2 WHERE telegram_id=$1", telegram_id, region
        )

    async def get_user(self, telegram_id: int) -> asyncpg.Record | None:
        return await self._pool().fetchrow(
            "SELECT * FROM users WHERE telegram_id=$1", telegram_id
        )

    async def save_calculation(self, telegram_id: int, *, car_data: dict[str, Any],
                               market_data: dict[str, Any], repair_estimate: dict[str, Any],
                               scores: dict[str, Any], final_report: str) -> int:
        value = await self._pool().fetchval(
            """INSERT INTO calculations
               (user_id, car_data, market_data, repair_estimate, scores, final_report)
               SELECT id, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, $6
               FROM users WHERE telegram_id=$1 RETURNING id""",
            telegram_id, json.dumps(car_data, ensure_ascii=False),
            json.dumps(market_data, ensure_ascii=False),
            json.dumps(repair_estimate, ensure_ascii=False),
            json.dumps(scores, ensure_ascii=False), final_report,
        )
        if value is None:
            raise RuntimeError("Пользователь не найден")
        return int(value)

    async def get_cache(self, prompt_hash: str) -> dict[str, Any] | None:
        value = await self._pool().fetchval(
            "SELECT response FROM ai_cache WHERE prompt_hash=$1 AND expires_at > NOW()",
            prompt_hash,
        )
        return dict(value) if value is not None else None

    async def set_cache(self, prompt_hash: str, response: dict[str, Any], hours: int = 24) -> None:
        expires = datetime.now(timezone.utc) + timedelta(hours=hours)
        await self._pool().execute(
            """INSERT INTO ai_cache (prompt_hash, response, expires_at)
               VALUES ($1, $2::jsonb, $3)
               ON CONFLICT (prompt_hash) DO UPDATE SET response=EXCLUDED.response,
               created_at=NOW(), expires_at=EXCLUDED.expires_at""",
            prompt_hash, json.dumps(response, ensure_ascii=False), expires,
        )


async def _read_text(path: Path) -> str:
    # Небольшие локальные файлы читаются в потоке, чтобы не блокировать event loop.
    import asyncio
    return await asyncio.to_thread(path.read_text, encoding="utf-8")

