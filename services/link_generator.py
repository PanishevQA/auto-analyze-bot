from urllib.parse import quote_plus


def generate_search_links(search_query: str) -> dict[str, str]:
    encoded = quote_plus(search_query.strip())
    return {
        "auto_ru": f"https://auto.ru/parts/search/?text={encoded}",
        "drom": f"https://baza.drom.ru/sell_spare_parts/?query={encoded}",
        "exist": f"https://exist.ru/Price/?pcode={encoded}",
    }

