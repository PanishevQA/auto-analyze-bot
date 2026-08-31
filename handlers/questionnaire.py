from typing import Callable

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from utils.formatters import format_summary
from utils.validators import (validate_car_model, validate_engine, validate_issues,
                              validate_mileage, validate_optional_text, validate_price,
                              validate_year)

router = Router()


class Questionnaire(StatesGroup):
    waiting_car_model = State()
    waiting_year = State()
    waiting_mileage = State()
    waiting_engine = State()
    waiting_price = State()
    waiting_listing_description = State()
    waiting_photo_damage = State()
    waiting_issues = State()
    waiting_confirmation = State()


@router.callback_query(F.data == "analyze")
async def begin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Questionnaire.waiting_car_model)
    await callback.message.answer("Введите марку и модель:")
    await callback.answer()


async def _save(message: Message, state: FSMContext, field: str, validator: Callable,
                next_state: State, question: str) -> None:
    try:
        value = validator(message.text or "")
    except ValueError as error:
        await message.answer(f"❌ {error}\n{question}")
        return
    await state.update_data(**{field: value})
    await state.set_state(next_state)
    await message.answer(question)


@router.message(Questionnaire.waiting_car_model)
async def car_model(message: Message, state: FSMContext) -> None:
    await _save(message, state, "car_model", validate_car_model, Questionnaire.waiting_year,
                "Введите год выпуска:")


@router.message(Questionnaire.waiting_year)
async def year(message: Message, state: FSMContext) -> None:
    await _save(message, state, "year", validate_year, Questionnaire.waiting_mileage,
                "Введите пробег в км:")


@router.message(Questionnaire.waiting_mileage)
async def mileage(message: Message, state: FSMContext) -> None:
    await _save(message, state, "mileage", validate_mileage, Questionnaire.waiting_engine,
                "Укажите двигатель и КПП:")


@router.message(Questionnaire.waiting_engine)
async def engine(message: Message, state: FSMContext) -> None:
    await _save(message, state, "engine", validate_engine, Questionnaire.waiting_price,
                "Введите цену покупки в ₽:")


@router.message(Questionnaire.waiting_price)
async def price(message: Message, state: FSMContext) -> None:
    await _save(
        message, state, "price", validate_price, Questionnaire.waiting_listing_description,
        "Вставьте описание из объявления или отправьте /skip:",
    )


@router.message(Questionnaire.waiting_listing_description)
async def listing_description(message: Message, state: FSMContext) -> None:
    await _save(
        message, state, "listing_description", validate_optional_text,
        Questionnaire.waiting_photo_damage,
        "Опишите повреждения, которые видны на фото, или отправьте /skip:",
    )


@router.message(Questionnaire.waiting_photo_damage)
async def photo_damage(message: Message, state: FSMContext) -> None:
    await _save(
        message, state, "photo_damage", validate_optional_text,
        Questionnaire.waiting_issues,
        "Опишите остальные известные проблемы или отправьте /skip:",
    )


@router.message(Questionnaire.waiting_issues)
async def issues(message: Message, state: FSMContext) -> None:
    await state.update_data(user_issues=validate_issues(message.text))
    data = await state.get_data()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить и провести анализ", callback_data="confirm")],
        [InlineKeyboardButton(text="✏️ Редактировать данные", callback_data="edit")],
    ])
    await state.set_state(Questionnaire.waiting_confirmation)
    await message.answer(format_summary(data), reply_markup=keyboard)


@router.callback_query(Questionnaire.waiting_confirmation, F.data == "edit")
async def edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Questionnaire.waiting_car_model)
    await callback.message.answer("Введите марку и модель заново:")
    await callback.answer()
