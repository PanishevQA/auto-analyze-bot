from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from utils.keyboards import HELP,HOME,SETTINGS,main_menu

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
    await callback.message.edit_text(f"Регион: <b>{region}</b>")
    await callback.message.answer("Главное меню",reply_markup=main_menu())
    await callback.answer()

@router.message(F.text.in_({HOME,"🏠 Главное меню"}))
async def home(message:Message): await message.answer("Главное меню",reply_markup=main_menu())

@router.message(F.text==HELP)
async def help_button(message:Message):
    await message.answer("Бот выполняет предварительную оценку. Начните с кнопки «🚗 Новый анализ». Фотографии не заменяют диагностику.",reply_markup=main_menu())

@router.message(F.text==SETTINGS)
async def settings_button(message:Message,settings):
    mode="🧪 тестовый" if settings.test_mode else "боевой"
    await message.answer(f"⚙️ Настройки\nРежим APIpoint: {mode}\nСостояние запчастей: {settings.parts_default_condition}\nЦелевая прибыль: {settings.target_profit_rub} ₽",reply_markup=main_menu())
