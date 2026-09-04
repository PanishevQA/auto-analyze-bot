from datetime import datetime,timezone
import logging
from schemas import (DefectStatus, PartCondition, PartPriceEstimate, PartSearchQuery,
                     PartsStatus, RepairEstimate, VehicleSpec, VisibleDefect)
from services.parts_matcher import infer_side_position
from services.yandex_parts_agent import YandexPartsAgent
from services.parts import CachedPartsProvider, UnconfiguredPartsProvider
from services.manual_parts_provider import ManualBrowserPartsProvider
from services.browser_parts_provider import BrowserPartsProvider
logger=logging.getLogger(__name__)

async def build_parts_provider(settings, yandex_client=None):
    """Единственная фабрика выбора режима; TEST_MODE на parts search не влияет."""
    if settings.parts_search_mode=="DISABLED": return UnconfiguredPartsProvider()
    if settings.parts_search_mode=="MANUAL_BROWSER":
        return ManualBrowserPartsProvider(settings.drom_baza_start_url,settings.parts_min_matched_offers)
    browser=BrowserPartsProvider(settings.drom_baza_start_url,headless=settings.parts_browser_headless,
        timeout_seconds=settings.parts_browser_timeout_seconds,max_offers=settings.parts_browser_max_offers,
        min_offers=settings.parts_min_matched_offers,match_confidence=float(settings.parts_match_confidence))
    return CachedPartsProvider(browser,settings.parts_price_cache_ttl_hours)

class PartsSearchOrchestrator:
    def __init__(self, provider, *, default_condition: PartCondition=PartCondition.NEW, agent=None):
        self.provider=provider; self.agent=agent or YandexPartsAgent(); self.default_condition=default_condition
    async def estimate(self, vehicle: VehicleSpec, defects: list[VisibleDefect], repairs: RepairEstimate):
        by_id={item.defect_id:item for item in repairs.items}; results=[]
        for defect in defects:
            item=by_id.get(defect.defect_id)
            if not item or not item.requires_part or defect.status is not DefectStatus.CONFIRMED: continue
            side,position=infer_side_position(defect.part)
            try: plan=await self.agent.create_plan(vehicle,defect.part,side,position,self.default_condition)
            except Exception as error:
                logger.warning("Yandex parts plan unavailable defect_id=%s error=%s",defect.defect_id,type(error).__name__)
                plan=self.agent.build_plan(vehicle,defect.part,side,position,self.default_condition)
            item.part_name=defect.part; item.side=side; item.position=position
            query=PartSearchQuery(defect_id=defect.defect_id,vin=vehicle.vin,make=vehicle.make,model=vehicle.model,year=vehicle.year,
                generation=vehicle.generation,part_name=defect.part,side=side,position=position,
                search_phrase=plan.query,quantity=item.quantity,region=vehicle.region,condition=self.default_condition)
            try: quote=await self.provider.search(query)
            except Exception as error:
                logger.warning("Parts lookup failed defect_id=%s error=%s",item.defect_id,type(error).__name__)
                quote=PartPriceEstimate(status=PartsStatus.ERROR,missing_parts=[defect.part],
                    fetched_at=datetime.now(timezone.utc))
            query_data=dict(quote.query_data or {})
            query_data.update(query.model_dump(mode="json",exclude={"vin"}))
            query_data.update(plan.model_dump(mode="json"))
            results.append(quote.model_copy(update={"defect_id":defect.defect_id,"query_data":query_data}))
        return results
