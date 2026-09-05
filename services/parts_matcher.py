import re
from decimal import Decimal

from schemas import MatchStatus, PartCondition, PartOffer, PartSearchQuery

UNTRUSTED_TAGS = re.compile(r"<[^>]*>|[\x00-\x08\x0b\x0c\x0e-\x1f]")

def sanitize_listing_text(value: str | None, limit: int = 300) -> str | None:
    if value is None: return None
    return UNTRUSTED_TAGS.sub("", value)[:limit].strip()

def infer_side_position(part: str) -> tuple[str | None, str | None]:
    text=part.casefold()
    side="LEFT" if any(x in text for x in ("лев", "left")) else "RIGHT" if any(x in text for x in ("прав", "right")) else None
    position="FRONT" if any(x in text for x in ("перед", "front")) else "REAR" if any(x in text for x in ("зад", "rear")) else None
    return side,position

def match_offer(query: PartSearchQuery, offer: PartOffer) -> PartOffer:
    title=(sanitize_listing_text(offer.part_name) or "").casefold()
    required=[query.make.casefold(),query.model.casefold(),query.part_name.casefold()]
    rejected=[]
    opposites={"LEFT":["прав","right"],"RIGHT":["лев","left"],"FRONT":["зад","rear"],"REAR":["перед","front"]}
    for marker in opposites.get(query.side or "",[])+opposites.get(query.position or "",[]):
        if marker in title: rejected.append("не совпадает сторона/позиция")
    if any(word in title for word in ("креплен", "ремкомплект", "стекло фары")) and "креплен" not in query.part_name.casefold():
        rejected.append("предлагается компонент, а не деталь в сборе")
    missing=[token for token in required if token not in title]
    if rejected or len(missing)>=2: status,confidence=MatchStatus.REJECTED,Decimal("0")
    elif not missing: status,confidence=MatchStatus.EXACT,Decimal("0.95")
    else: status,confidence=MatchStatus.LIKELY,Decimal("0.80")
    return offer.model_copy(update={"part_name":sanitize_listing_text(offer.part_name) or "",
        "seller":sanitize_listing_text(offer.seller),"delivery_text":sanitize_listing_text(offer.delivery_text),
        "match_status":status,"match_confidence":confidence,
        "match_reasons":rejected or (["совпали обязательные признаки"] if not missing else ["частичное совпадение"] )})


def enforce_compatibility(query: PartSearchQuery, offer: PartOffer,
                          confidence_threshold: Decimal) -> PartOffer:
    """Apply non-overridable deterministic constraints after any AI classification."""
    rules = match_offer(query, offer)
    reasons = list(offer.match_reasons)
    if offer.condition is not query.condition:
        reasons.append("не совпадает состояние детали")
        return offer.model_copy(update={"match_status": MatchStatus.REJECTED,
            "match_confidence": Decimal("0"), "match_reasons": reasons})
    if rules.match_status is MatchStatus.REJECTED:
        return offer.model_copy(update={"match_status": MatchStatus.REJECTED,
            "match_confidence": Decimal("0"), "match_reasons": list(dict.fromkeys(reasons+rules.match_reasons))})
    if offer.match_status in {MatchStatus.EXACT,MatchStatus.LIKELY} and offer.match_confidence < confidence_threshold:
        reasons.append("уверенность ниже установленного порога")
        return offer.model_copy(update={"match_status": MatchStatus.REJECTED,"match_reasons":reasons})
    return offer
