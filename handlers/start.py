from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()
REGIONS = ("Новосибирск и НО", "Москва и МО", "Санкт-Петербург и ЛО",
           "Екатеринбург", "Красноярск", "Весь РФ")


def region_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"region:{index}")]
        for index, name in enumerate(REGIONS)
    ])


def analyze_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚗 Проанализировать авто", callback_data="analyze")
    ]])


@router.message(CommandStart())
async def start(message: Message, db) -> None:
    await db.upsert_user(message.from_user.id)
    await message.answer("Выберите регион анализа:", reply_markup=region_keyboard())


@router.callback_query(F.data.startswith("region:"))
async def choose_region(callback: CallbackQuery, db) -> None:
    try:
        region = REGIONS[int(callback.data.split(":", 1)[1])]
    except (ValueError, IndexError):
        await callback.answer("Неизвестный регион", show_alert=True)
        return
    await db.set_region(callback.from_user.id, region)
    await callback.message.edit_text(f"Регион: <b>{region}</b>", reply_markup=analyze_keyboard())
    await callback.answer()

