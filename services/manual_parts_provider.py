from datetime import datetime, timezone
from urllib.parse import urlsplit

from schemas import PartOffer, PartPriceEstimate, PartSearchQuery, PartsStatus
from services.parts import normalize_offers

def validate_drom_baza_url(url: str) -> str:
    parsed=urlsplit(url.strip())
    if parsed.scheme!="https" or parsed.hostname!="baza.drom.ru" or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError("Разрешены только HTTPS-ссылки baza.drom.ru")
    return parsed._replace(fragment="").geturl()

class ManualBrowserPartsProvider:
    """Не открывает Drom: принимает только явно переданные пользователем карточки."""
    def __init__(self, start_url: str, min_offers: int = 3) -> None:
        self.start_url=validate_drom_baza_url(start_url); self.min_offers=min_offers

    async def search(self, query: PartSearchQuery) -> PartPriceEstimate:
        return PartPriceEstimate(status=PartsStatus.UNAVAILABLE,provider="DROM_BAZA_MANUAL",
            fetched_at=datetime.now(timezone.utc),missing_parts=[query.part_name],
            query_data={"manual_url":self.start_url,"part_name":query.part_name})

    def instruction(self, vehicle: str, query: str, condition: str) -> str:
        return (f"🔎 Требуется найти запчасть\n\nАвтомобиль: {vehicle}\nДеталь: {query}\n"
                f"Состояние: {condition}\n\nОткройте Drom Базу и пришлите от 3 до 10 "
                "ссылок на подходящие объявления или скриншоты выдачи.")

    def normalize_submitted(self, query: PartSearchQuery, offers: list[PartOffer]) -> PartPriceEstimate:
        for offer in offers:
            if offer.offer_url: validate_drom_baza_url(str(offer.offer_url))
        return normalize_offers(offers,condition=query.condition,quantity=query.quantity,
            provider="DROM_BAZA_MANUAL",min_offers=self.min_offers)
