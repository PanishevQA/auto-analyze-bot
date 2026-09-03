import re
from pydantic import BaseModel, ConfigDict, Field
from schemas import PartCondition, PartSearchQuery, VehicleSpec

class PartsSearchPlan(BaseModel):
    model_config=ConfigDict(extra="forbid")
    query: str = Field(min_length=1,max_length=300)
    normalized_part_name: str = Field(min_length=1,max_length=150)
    required_tokens: list[str]; optional_tokens: list[str]; exclude_tokens: list[str]
    oem_number: str | None = None

class YandexPartsAgent:
    """Ограниченный доменный агент: не получает open_url/click/JavaScript tools."""
    TOOL_NAME="search_spare_parts"
    URL=re.compile(r"https?://|www\.",re.I)

    def build_plan(self, vehicle: VehicleSpec, part_name: str, side: str | None,
                   position: str | None, condition: PartCondition) -> PartsSearchPlan:
        normalized=" ".join(x for x in (position,side,part_name) if x).lower()
        query=" ".join(x for x in (normalized,vehicle.make,vehicle.model,str(vehicle.year)) if x)
        return PartsSearchPlan(query=query,normalized_part_name=normalized,
            required_tokens=[vehicle.make,vehicle.model,part_name]+([side] if side else []),
            optional_tokens=[str(vehicle.year)]+([vehicle.generation] if vehicle.generation else []),
            exclude_tokens=["ремкомплект","крепление","стекло фары"],oem_number=None)

    def validate_tool_call(self, values: dict, *, max_offers: int) -> PartSearchQuery:
        if set(values)-{"query","make","model","year","generation","part_name","side","position","condition","region","max_offers"}:
            raise ValueError("Недопустимые параметры browser tool")
        query=str(values.get("query", ""))
        if len(query)>300 or self.URL.search(query) or any(ord(c)<32 for c in query):
            raise ValueError("Небезопасный поисковый запрос")
        if int(values.get("max_offers",0)) not in range(1,max_offers+1): raise ValueError("Превышен max_offers")
        return PartSearchQuery(**{key:value for key,value in values.items() if key not in {"query","max_offers"}})
