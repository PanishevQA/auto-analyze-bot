from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from handlers.start import REGIONS
from utils.formatters import money
from utils.keyboards import SETTINGS, main_menu
from utils.validators import validate_price

router = Router()


class UserSettings(StatesGroup):
    custom_profit = State()


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Регион", callback_data="settings:region")],
        [InlineKeyboardButton(text="💰 Целевая прибыль", callback_data="settings:profit")],
        [InlineKeyboardButton(text="🧩 Состояние запчастей", callback_data="settings:condition")],
        [InlineKeyboardButton(text="🧪 Режим APIpoint", callback_data="settings:mode")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="nav:home")],
    ])


@router.message(F.text == SETTINGS)
async def show_settings(message: Message, state: FSMContext, db, settings) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)
    condition = (user.parts_condition if user and user.parts_condition else settings.parts_default_condition)
    target = user.target_profit_rub if user and user.target_profit_rub is not None else settings.target_profit_rub
    mode = "🧪 тестовый" if settings.test_mode else "боевой"
    await message.answer(f"⚙️ Настройки\nРегион: {user.region if user else 'Весь РФ'}\n"
        f"Целевая прибыль: {money(target)} ₽\nСостояние запчастей: {'Новые' if condition=='NEW' else 'Б/у'}\n"
        f"Режим APIpoint: {mode}", reply_markup=settings_keyboard())


@router.callback_query(F.data == "settings:region")
async def choose_region_menu(callback: CallbackQuery) -> None:
    keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=name,callback_data=f"settings:region:{i}")]
        for i,name in enumerate(REGIONS)]+[[InlineKeyboardButton(text="⬅️ Назад",callback_data="settings:back")]])
    await callback.message.answer("Выберите регион:",reply_markup=keyboard); await callback.answer()


@router.callback_query(F.data.startswith("settings:region:"))
async def save_region(callback: CallbackQuery, db) -> None:
    try: region=REGIONS[int(callback.data.rsplit(":",1)[1])]
    except (ValueError,IndexError): await callback.answer("Неизвестный регион",show_alert=True); return
    await db.set_region(callback.from_user.id,region); await callback.answer("Сохранено")
    await callback.message.answer(f"Регион: {region}",reply_markup=main_menu())


@router.callback_query(F.data == "settings:profit")
async def choose_profit(callback: CallbackQuery) -> None:
    values=(30000,40000,50000,75000,100000)
    rows=[[InlineKeyboardButton(text=f"{money(value)} ₽",callback_data=f"settings:profit:{value}")] for value in values]
    rows.append([InlineKeyboardButton(text="✏️ Указать свою",callback_data="settings:profit:custom")])
    await callback.message.answer("Выберите целевую прибыль:",reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)); await callback.answer()


@router.callback_query(F.data.startswith("settings:profit:"))
async def save_profit(callback: CallbackQuery, state: FSMContext, db) -> None:
    raw=callback.data.rsplit(":",1)[1]
    if raw=="custom":
        await state.set_state(UserSettings.custom_profit); await callback.message.answer("Введите целевую прибыль, ₽:"); await callback.answer(); return
    await db.set_user_preferences(callback.from_user.id,target_profit_rub=int(raw)); await callback.answer("Сохранено")
    await callback.message.answer("Целевая прибыль сохранена.",reply_markup=main_menu())


@router.message(UserSettings.custom_profit)
async def custom_profit(message: Message, state: FSMContext, db) -> None:
    try: value=validate_price(message.text or "")
    except ValueError as error: await message.answer(f"❌ {error}"); return
    await db.set_user_preferences(message.from_user.id,target_profit_rub=value); await state.clear()
    await message.answer("Целевая прибыль сохранена.",reply_markup=main_menu())


@router.callback_query(F.data == "settings:condition")
async def choose_condition(callback: CallbackQuery) -> None:
    await callback.message.answer("Состояние запчастей:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Новые",callback_data="settings:condition:NEW"),
         InlineKeyboardButton(text="Б/у",callback_data="settings:condition:USED")]])); await callback.answer()


@router.callback_query(F.data.startswith("settings:condition:"))
async def save_condition(callback: CallbackQuery, db) -> None:
    value=callback.data.rsplit(":",1)[1]
    if value not in {"NEW","USED"}: await callback.answer("Неизвестное значение",show_alert=True); return
    await db.set_user_preferences(callback.from_user.id,parts_condition=value); await callback.answer("Сохранено")
    await callback.message.answer("Состояние запчастей сохранено.",reply_markup=main_menu())


@router.callback_query(F.data == "settings:mode")
async def api_mode(callback: CallbackQuery, settings) -> None:
    await callback.answer("🧪 тестовый" if settings.test_mode else "боевой",show_alert=True)


@router.callback_query(F.data == "settings:back")
async def settings_back(callback: CallbackQuery) -> None:
    await callback.message.answer("Настройки",reply_markup=settings_keyboard()); await callback.answer()
