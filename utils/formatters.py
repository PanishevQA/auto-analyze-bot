import html
from typing import Any


def money(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_summary(data: dict[str, Any]) -> str:
    return (
        f"<b>Проверьте данные</b>\n\n🚗 {html.escape(str(data['make']))} {html.escape(str(data['model']))}\n"
        f"📅 {data['year']} · 🛣 {money(int(data['mileage_km']))} км\n"
        f"Поколение: {html.escape(str(data.get('generation') or 'не указано'))}\n"
        f"Двигатель: {html.escape(str(data.get('engine_volume_l') or 'не указан'))}; "
        f"{html.escape(str(data.get('fuel_type') or 'UNKNOWN'))}; {html.escape(str(data.get('transmission') or 'UNKNOWN'))}\n"
        f"💰 {money(int(data['asking_price_rub']))} ₽ · 📷 {len(data.get('photos', []))} фото\n"
        f"📄 {html.escape(str(data.get('seller_description') or 'Описание не указано'))}"
    )
