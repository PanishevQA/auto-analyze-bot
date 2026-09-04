from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from utils.keyboards import CANCEL, HELP, HISTORY, HOME, NEW_ANALYSIS, SETTINGS, main_menu

router = Router()
CONTROL_TEXTS = frozenset({CANCEL, HELP, HISTORY, HOME, NEW_ANALYSIS, SETTINGS})


@router.message(F.text == HOME)
async def home(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_menu())


@router.message(F.text == CANCEL)
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено", reply_markup=main_menu())


@router.callback_query(F.data == "nav:home")
async def callback_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer("Главное меню", reply_markup=main_menu())


@router.callback_query(F.data == "nav:cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer("Действие отменено", reply_markup=main_menu())


@router.callback_query(F.data == "nav:back")
async def callback_back(callback: CallbackQuery, state: FSMContext) -> None:
    from handlers.questionnaire import go_back
    await go_back(callback.message, state)
    await callback.answer()


@router.message(F.text == NEW_ANALYSIS)
async def new_analysis(message: Message, state: FSMContext, db, settings) -> None:
    from handlers.questionnaire import begin_for_message
    await begin_for_message(message, state, db, message.from_user.id, settings)


@router.message(F.text == HISTORY)
async def history(message: Message, state: FSMContext, db) -> None:
    from handlers.history import show_history_buttons
    await state.clear()
    await show_history_buttons(message, db)


@router.message(F.text == HELP)
async def help_page(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Бот выполняет предварительную оценку. Начните с кнопки «🚗 Новый анализ».", reply_markup=main_menu())
