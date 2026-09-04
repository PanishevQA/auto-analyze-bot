from aiogram.types import Message


async def answer_long_html(message: Message, text: str, *, disable_web_page_preview: bool = True) -> None:
    """Отправляет длинный отчет частями, не разрывая строки с HTML-разметкой."""
    for chunk in split_html_messages(text):
        await message.answer(chunk, disable_web_page_preview=disable_web_page_preview)


def split_html_messages(text: str, limit: int = 3_900) -> list[str]:
    """Делит только между строками; слишком длинную строку отклоняет, а не ломает HTML-тег."""
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            raise ValueError("Строка отчета превышает безопасный лимит Telegram")
        if len(current) + len(line) > limit and current:
            chunks.append(current.rstrip())
            current = ""
        current += line
    if current.strip():
        chunks.append(current.rstrip())
    return chunks
