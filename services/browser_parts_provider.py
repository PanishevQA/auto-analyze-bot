from __future__ import annotations
import importlib
import re
import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser

from schemas import MatchStatus, PartCondition, PartOffer, PartPriceEstimate, PartSearchQuery, PartsStatus
from services.manual_parts_provider import validate_drom_baza_url
from services.parts import normalize_offers
from services.parts_matcher import match_offer, sanitize_listing_text

BLOCK_MARKERS=("captcha","подтвердите, что вы человек","access denied","необычный трафик")

class BrowserBlocked(RuntimeError): pass

class _CardsParser(HTMLParser):
    def __init__(self): super().__init__(); self.cards=[]; self.current=None; self.capture=None; self.card_tag=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); classes=a.get("class","")
        if tag in {"article","div"} and ("offer-card" in classes or a.get("data-testid")=="offer-card"):
            self.current={"title":"","price":"","old":"","href":a.get("data-url")}
            self.card_tag=tag
        if self.current is not None:
            if tag=="a" and a.get("href"): self.current["href"]=a["href"]
            if "current-price" in classes or a.get("data-testid")=="current-price": self.capture="price"
            elif "old-price" in classes or a.get("data-testid")=="old-price": self.capture="old"
            elif tag in {"h2","h3"} or "title" in classes: self.capture="title"
    def handle_data(self,data):
        if self.current is not None and self.capture: self.current[self.capture]+=data
    def handle_endtag(self,tag):
        if self.current is not None and tag==self.card_tag:
            self.cards.append(self.current); self.current=None
        self.capture=None

def _rubles(text: str) -> int | None:
    values=re.findall(r"\d[\d\s\u00a0]*",text)
    return int(re.sub(r"\D","",values[-1])) if values else None

def parse_visible_cards(html: str, *, condition: PartCondition=PartCondition.NEW) -> list[PartOffer]:
    lowered=html.casefold()
    if any(marker in lowered for marker in BLOCK_MARKERS): raise BrowserBlocked("Drom остановил автоматизированный доступ")
    parser=_CardsParser(); parser.feed(html); now=datetime.now(timezone.utc); offers=[]
    for card in parser.cards:
        price=_rubles(card["price"]); href=card.get("href")
        if not price or not href: continue
        if href.startswith("/"): href="https://baza.drom.ru"+href
        try: href=validate_drom_baza_url(href)
        except ValueError: continue
        offers.append(PartOffer(provider="DROM_BAZA_BROWSER",part_name=sanitize_listing_text(card["title"]) or "Деталь",
            condition=condition,unit_price_rub=price,old_price_rub=_rubles(card["old"]),in_stock=True,
            offer_url=href,fetched_at=now,source="DROM_BAZA_BROWSER"))
    return offers

class BrowserPartsProvider:
    def __init__(self, start_url: str, *, headless: bool=True, timeout_seconds: int=30,
                 max_offers: int=20, min_offers: int=3, match_confidence: float=.8) -> None:
        self.start_url=validate_drom_baza_url(start_url); self.headless=headless
        self.timeout_ms=timeout_seconds*1000; self.max_offers=min(max_offers,20)
        self.min_offers=min_offers; self.match_confidence=match_confidence
        self._playwright=self._browser=None
        self._lock=asyncio.Lock()
    async def start(self):
        module=importlib.import_module("playwright.async_api")
        self._playwright=await module.async_playwright().start()
        self._browser=await self._playwright.chromium.launch(headless=self.headless)
    async def close(self):
        if self._browser: await self._browser.close()
        if self._playwright: await self._playwright.stop()
    async def search(self, query: PartSearchQuery) -> PartPriceEstimate:
        async with self._lock:
            return await self._search_once(query)
    async def _search_once(self, query: PartSearchQuery) -> PartPriceEstimate:
        if not self._browser: raise RuntimeError("BrowserPartsProvider не запущен")
        page=await self._browser.new_page(); page.set_default_timeout(self.timeout_ms)
        try:
            await page.goto(self.start_url,wait_until="domcontentloaded")
            content=(await page.locator("body").inner_text()).casefold()
            if any(marker in content for marker in BLOCK_MARKERS): return PartPriceEstimate(status=PartsStatus.BLOCKED,provider="DROM_BAZA_BROWSER",missing_parts=[query.part_name])
            field=page.get_by_placeholder("Название запчасти или её номер")
            await field.fill(query.part_name); await page.get_by_role("button",name="Найти").click()
            await page.wait_for_load_state("domcontentloaded")
            offers=parse_visible_cards(await page.content(),condition=query.condition)[:self.max_offers]
            matched=[match_offer(query,o) for o in offers]
            relevant=[o for o in matched if o.match_status is MatchStatus.EXACT or
                      (o.match_status is MatchStatus.LIKELY and float(o.match_confidence)>=self.match_confidence)]
            return normalize_offers(relevant,condition=query.condition,quantity=query.quantity,
                provider="DROM_BAZA_BROWSER",min_offers=self.min_offers)
        except BrowserBlocked:
            return PartPriceEstimate(status=PartsStatus.BLOCKED,provider="DROM_BAZA_BROWSER",missing_parts=[query.part_name])
        finally: await page.close()

class FixtureBrowserPartsProvider:
    def __init__(self, html: str, min_offers: int=3): self.html=html; self.min_offers=min_offers
    async def search(self, query: PartSearchQuery) -> PartPriceEstimate:
        try: offers=[match_offer(query,o) for o in parse_visible_cards(self.html,condition=query.condition)]
        except BrowserBlocked: return PartPriceEstimate(status=PartsStatus.BLOCKED,provider="DROM_BAZA_BROWSER")
        relevant=[o for o in offers if o.match_status in {MatchStatus.EXACT,MatchStatus.LIKELY}]
        return normalize_offers(relevant,condition=query.condition,quantity=query.quantity,
            provider="DROM_BAZA_BROWSER",min_offers=self.min_offers)
