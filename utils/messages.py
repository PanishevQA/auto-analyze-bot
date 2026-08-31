from aiogram.types import Message


async def answer_long_html(message: Message, text: str, *, disable_web_page_preview: bool = True) -> None:
    """Отправляет длинный отчет частями, не разрывая строки с HTML-разметкой."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > 3_900 and current:
            chunks.append(current.rstrip())
            current = ""
        if len(line) > 3_900:
            # Пользовательские/AI-поля заранее ограничены, это лишь защитный fallback.
            chunks.extend(line[index:index + 3_900] for index in range(0, len(line), 3_900))
        else:
            current += line
    if current.strip():
        chunks.append(current.rstrip())
    for chunk in chunks:
        await message.answer(chunk, disable_web_page_preview=disable_web_page_preview)
