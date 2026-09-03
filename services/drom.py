from dataclasses import dataclass
import ipaddress
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from schemas import SourceMode


class InvalidDromUrl(ValueError): pass


@dataclass(frozen=True, slots=True)
class DromSource:
    source_url: str
    source_mode: SourceMode = SourceMode.MANUAL
    listing_id: str | None = None


class ManualDromAdapter:
    allowed_hosts = {"drom.ru", "www.drom.ru", "auto.drom.ru"}
    tracking_prefixes = ("utm_", "yclid", "gclid")

    async def validate(self, raw_url: str) -> DromSource:
        if len(raw_url) > 2048: raise InvalidDromUrl("Ссылка слишком длинная")
        parsed = urlsplit(raw_url.strip())
        if parsed.scheme != "https": raise InvalidDromUrl("Разрешен только HTTPS")
        if parsed.username or parsed.password: raise InvalidDromUrl("Учетные данные в URL запрещены")
        if parsed.port not in (None, 443): raise InvalidDromUrl("Нестандартный порт запрещен")
        host = (parsed.hostname or "").lower().rstrip(".")
        try: ipaddress.ip_address(host); raise InvalidDromUrl("IP-адрес запрещен")
        except ValueError as error:
            if isinstance(error, InvalidDromUrl): raise
        if host not in self.allowed_hosts: raise InvalidDromUrl("Разрешены только домены Drom")
        query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                           if not any(k.lower().startswith(prefix) for prefix in self.tracking_prefixes)])
        clean = urlunsplit(("https", host, parsed.path or "/", query, ""))
        tail = parsed.path.rstrip("/").split("/")[-1]
        listing_id = tail.removesuffix(".html") if tail.removesuffix(".html").isdigit() else None
        return DromSource(clean, listing_id=listing_id)
