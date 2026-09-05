from aiogram import F, Router
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data)
async def stale_callback(callback: CallbackQuery) -> None:
    """Safely reject callbacks left on messages from an older FSM/menu."""
    await callback.answer("Это меню устарело. Откройте главное меню", show_alert=True)
