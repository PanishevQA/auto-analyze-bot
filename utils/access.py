import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class OwnerAccessMiddleware(BaseMiddleware):
    def __init__(self, owner_ids: frozenset[int]) -> None:
        if not owner_ids:
            raise RuntimeError("Owner allowlist не настроен")
        self.owner_ids = owner_ids

    async def __call__(
        self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject, data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id not in self.owner_ids:
            logger.warning("Отклонена попытка доступа к личному боту; telegram_id=%s",
                           getattr(user, "id", "unknown"))
            return None
        return await handler(event, data)
