import html
from typing import Any


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_summary(data: dict[str, Any]) -> str:
    return (
        f"<b>Проверьте данные</b>\n\n🚗 {html.escape(data['car_model'])}\n"
        f"📅 {data['year']} · 🛣 {money(data['mileage'])} км\n"
        f"⚙️ {html.escape(data['engine'])}\n💰 {money(data['price'])} ₽\n"
        f"📄 <b>Описание объявления:</b> {html.escape(data['listing_description'])}\n"
        f"📷 <b>Повреждения на фото:</b> {html.escape(data['photo_damage'])}\n"
        f"🛠 <b>Дополнительные данные:</b> {html.escape(data['user_issues'])}"
    )
