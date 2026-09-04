from aiogram.types import KeyboardButton,ReplyKeyboardMarkup

NEW_ANALYSIS="🚗 Новый анализ"; HISTORY="📋 История"; SETTINGS="⚙️ Настройки"; HELP="ℹ️ Помощь"
CANCEL="❌ Отменить"; BACK="⬅️ Назад"; HOME="🏠 Главное меню"; SKIP="⏭ Пропустить"

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=NEW_ANALYSIS),KeyboardButton(text=HISTORY)],
        [KeyboardButton(text=SETTINGS),KeyboardButton(text=HELP)]],resize_keyboard=True,is_persistent=True)

def navigation(*,optional=False) -> ReplyKeyboardMarkup:
    rows=[[KeyboardButton(text=BACK),KeyboardButton(text=CANCEL)]]
    if optional: rows.insert(0,[KeyboardButton(text=SKIP)])
    rows.append([KeyboardButton(text=HOME)])
    return ReplyKeyboardMarkup(keyboard=rows,resize_keyboard=True)
