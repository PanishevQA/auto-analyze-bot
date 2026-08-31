import html

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from utils.formatters import money

router = Router()


def _date(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M")


@router.message(Command("history"))
async def history(message: Message, command: CommandObject, db) -> None:
    argument = (command.args or "").strip()
    if argument:
        await show_calculation(message, argument, db)
        return
    calculations = await db.get_user_calculations_list(message.from_user.id)
    if not calculations:
        await message.answer("📭 У вас пока нет сохраненных расчетов.")
        return
    rows = ["📋 <b>Ваши последние расчеты:</b>"]
    for item in calculations:
        rows.append(
            f"<b>#{item['id']}</b> — {html.escape(str(item['car_model']))} ({item['year']})\n"
            f"🛣 Пробег: {money(int(item['mileage']))} км\n📅 Дата: {_date(item['created_at'])}"
        )
    rows.append("💡 Для просмотра отчета используйте:\n<code>/history &lt;ID&gt;</code>\n"
                "Например: <code>/history 1</code>")
    await message.answer("\n\n".join(rows))


async def show_calculation(message: Message, argument: str, db) -> None:
    try:
        calculation_id = int(argument)
        if calculation_id <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Укажите положительный ID: <code>/history 1</code>")
        return
    calculation = await db.get_calculation_by_id(calculation_id, message.from_user.id)
    if calculation is None:
        await message.answer(
            f"❌ Расчет #{calculation_id} не найден или не принадлежит вам."
        )
        return
    heading = f"📊 <b>ОТЧЕТ #{calculation_id}</b> (от {_date(calculation['created_at'])})\n\n"
    await message.answer(heading + calculation["final_report"], disable_web_page_preview=True)
