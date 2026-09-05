from __future__ import annotations
import importlib
import re
import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser

from schemas import MatchStatus, PartCondition, PartOffer, PartPriceEstimate, PartSearchQuery, PartsStatus, VehicleSpec
from services.manual_parts_provider import validate_drom_baza_url
from services.parts import normalize_offers
from services.parts_matcher import enforce_compatibility, match_offer, sanitize_listing_text
from utils.money_parser import parse_rubles
from decimal import Decimal

BLOCK_MARKERS=("captcha","подтвердите, что вы человек","access denied","необычный трафик")

class BrowserBlocked(RuntimeError): pass

class _CardsParser(HTMLParser):
    def __init__(self): super().__init__(); self.cards=[]; self.current=None; self.capture=None; self.card_tag=None; self.depth=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs); classes=a.get("class","")
        if tag in {"article","div"} and ("offer-card" in classes or a.get("data-testid")=="offer-card"):
            self.current={"title":"","price":"","old":"","href":a.get("data-url"),
                "condition":a.get("data-condition"),"in_stock":a.get("data-in-stock"),
                "delivery":a.get("data-delivery"),"seller":a.get("data-seller"),"location":a.get("data-location")}
            self.card_tag=tag; self.depth=1
        elif self.current is not None: self.depth+=1
        if self.current is not None:
            if tag=="a" and a.get("href"): self.current["href"]=a["href"]
            if "current-price" in classes or a.get("data-testid")=="current-price": self.capture="price"
            elif "old-price" in classes or a.get("data-testid")=="old-price": self.capture="old"
            elif tag in {"h2","h3"} or "title" in classes: self.capture="title"
    def handle_data(self,data):
        if self.current is not None and self.capture: self.current[self.capture]+=data
    def handle_endtag(self,tag):
        if self.current is not None: self.depth-=1
        if self.current is not None and tag==self.card_tag and self.depth==0:
            self.cards.append(self.current); self.current=None
        self.capture=None

_rubles = parse_rubles

def parse_visible_cards(html: str, *, condition: PartCondition=PartCondition.UNKNOWN) -> list[PartOffer]:
    lowered=html.casefold()
    if any(marker in lowered for marker in BLOCK_MARKERS): raise BrowserBlocked("Drom остановил автоматизированный доступ")
    parser=_CardsParser(); parser.feed(html); now=datetime.now(timezone.utc); offers=[]
    for card in parser.cards:
        price=_rubles(card["price"]); href=card.get("href")
        if not price or not href: continue
        if href.startswith("/"): href="https://baza.drom.ru"+href
        try: href=validate_drom_baza_url(href)
        except ValueError: continue
        actual_condition=PartCondition(card["condition"]) if card.get("condition") in {"NEW","USED"} else condition
        stock={"true":True,"false":False}.get(str(card.get("in_stock")).lower())
        delivery=_rubles(card.get("delivery") or "") if card.get("delivery") not in {"0",0} else 0
        offers.append(PartOffer(provider="DROM_BAZA_BROWSER",part_name=sanitize_listing_text(card["title"]) or "Деталь",
            condition=actual_condition,unit_price_rub=price,old_price_rub=_rubles(card["old"]),in_stock=stock,
            delivery_price_rub=delivery,delivery_text=card.get("delivery"),seller=card.get("seller"),location=card.get("location"),
            offer_url=href,fetched_at=now,source="DROM_BAZA_BROWSER"))
    return offers

class BrowserPartsProvider:
    def __init__(self, start_url: str, *, headless: bool=True, timeout_seconds: int=30,
                 max_offers: int=20, min_offers: int=3, match_confidence: float=.8,agent=None) -> None:
        self.start_url=validate_drom_baza_url(start_url); self.headless=headless
        self.timeout_ms=timeout_seconds*1000; self.max_offers=min(max_offers,20)
        self.min_offers=min_offers; self.match_confidence=match_confidence
        self.agent=agent
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
            if not self._browser:
                try: await self.start()
                except Exception:
                    return PartPriceEstimate(defect_id=query.defect_id,status=PartsStatus.UNAVAILABLE,
                        provider="DROM_BAZA_BROWSER",missing_parts=[query.part_name])
            return await self._search_once(query)
    async def _search_once(self, query: PartSearchQuery) -> PartPriceEstimate:
        if not self._browser: raise RuntimeError("BrowserPartsProvider не запущен")
        page=await self._browser.new_page(); page.set_default_timeout(self.timeout_ms)
        try:
            await page.goto(self.start_url,wait_until="domcontentloaded")
            content=(await page.locator("body").inner_text()).casefold()
            if any(marker in content for marker in BLOCK_MARKERS): return PartPriceEstimate(status=PartsStatus.BLOCKED,provider="DROM_BAZA_BROWSER",missing_parts=[query.part_name])
            field=page.get_by_placeholder("Название запчасти или её номер")
            await field.fill(query.search_phrase or query.part_name); await page.get_by_role("button",name="Найти").click()
            await page.wait_for_load_state("domcontentloaded")
            offers=parse_visible_cards(await page.content())[:self.max_offers]
            if not offers:
                return PartPriceEstimate(defect_id=query.defect_id,status=PartsStatus.INSUFFICIENT_DATA,
                    provider="DROM_BAZA_BROWSER",missing_parts=[query.part_name])
            matched=[match_offer(query,o) for o in offers]; metadata={"matching_source":"RULES_FALLBACK","fallback_used":True}
            if self.agent:
                vehicle=VehicleSpec(make=query.make,model=query.model,
                    year=query.year,generation=query.generation,asking_price_rub=1,region=query.region)
                try: matched,metadata=await self.agent.classify_offers(vehicle,query,offers)
                except Exception: pass
            matched=[enforce_compatibility(query,o,Decimal(str(self.match_confidence))) for o in matched]
            relevant=[o for o in matched if o.match_status is MatchStatus.EXACT or
                      (o.match_status is MatchStatus.LIKELY and float(o.match_confidence)>=self.match_confidence)]
            estimate=normalize_offers(relevant,condition=query.condition,quantity=query.quantity,
                provider="DROM_BAZA_BROWSER",min_offers=self.min_offers)
            if metadata.get("fallback_used") and estimate.status is PartsStatus.READY:
                estimate=estimate.model_copy(update={"status":PartsStatus.INSUFFICIENT_DATA})
            return estimate.model_copy(update={"defect_id":query.defect_id,"query_data":metadata})
        except BrowserBlocked:
            return PartPriceEstimate(status=PartsStatus.BLOCKED,provider="DROM_BAZA_BROWSER",missing_parts=[query.part_name])
        finally: await page.close()

class FixtureBrowserPartsProvider:
    def __init__(self, html: str, min_offers: int=3): self.html=html; self.min_offers=min_offers
    async def search(self, query: PartSearchQuery) -> PartPriceEstimate:
        try: offers=[match_offer(query,o) for o in parse_visible_cards(self.html)]
        except BrowserBlocked: return PartPriceEstimate(status=PartsStatus.BLOCKED,provider="DROM_BAZA_BROWSER")
        if not offers: return PartPriceEstimate(defect_id=query.defect_id,status=PartsStatus.INSUFFICIENT_DATA,provider="DROM_BAZA_BROWSER")
        relevant=[o for o in offers if o.match_status in {MatchStatus.EXACT,MatchStatus.LIKELY}]
        return normalize_offers(relevant,condition=query.condition,quantity=query.quantity,
            provider="DROM_BAZA_BROWSER",min_offers=self.min_offers)
