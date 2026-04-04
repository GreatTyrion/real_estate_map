import html as html_lib
import json
import re
from typing import Any, Iterator

from bs4 import BeautifulSoup

LISTING_PATH_RE = re.compile(r"/v-(?:house-for-sale|real-estate)/", re.I)


def _flatten_json_ld(data: Any) -> Iterator[dict]:
    if isinstance(data, list):
        for item in data:
            yield from _flatten_json_ld(item)
        return
    if not isinstance(data, dict):
        return
    graph = data.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            yield from _flatten_json_ld(item)
        return
    yield data


def iter_json_ld_dicts(markup: bytes | str) -> Iterator[dict]:
    soup = BeautifulSoup(markup, "html.parser")
    for script in soup.find_all("script", attrs={"type": True}):
        st = (script.get("type") or "").lower()
        if "ld+json" not in st:
            continue
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        yield from _flatten_json_ld(data)


def listing_urls_from_search(markup: bytes | str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for obj in iter_json_ld_dicts(markup):
        if obj.get("@type") != "ItemList":
            continue
        for el in obj.get("itemListElement") or []:
            if not isinstance(el, dict):
                continue
            item = el.get("item")
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if isinstance(url, str) and url.startswith("http"):
                if url not in seen:
                    seen.add(url)
                    out.append(url)
    if out:
        return out

    soup = BeautifulSoup(markup, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not isinstance(href, str):
            continue
        if LISTING_PATH_RE.search(href) and re.search(r"/\d+/?$", href):
            full = href if href.startswith("http") else f"https://www.kijiji.ca{href}"
            if full not in seen:
                seen.add(full)
                out.append(full)
    return out


def _unescape_text(s: str) -> str:
    return html_lib.unescape(s).strip()


def _format_address(addr: Any) -> str:
    if isinstance(addr, str):
        return _unescape_text(addr)
    if isinstance(addr, dict):
        street = addr.get("streetAddress")
        locality = addr.get("addressLocality")
        region = addr.get("addressRegion")
        postal = addr.get("postalCode")
        country = addr.get("addressCountry")
        parts = [p for p in (street, locality, region, postal, country) if p]
        return ", ".join(_unescape_text(str(p)) for p in parts)
    return "Not available"


def _price_from_offers(offers: Any) -> str:
    if not isinstance(offers, dict):
        return "Not available"
    price = offers.get("price")
    if price is None:
        return "Not available"
    try:
        num = float(price)
        return f"${num:,.2f}"
    except (TypeError, ValueError):
        return _unescape_text(str(price))


def _lat_lon_from_listing(obj: dict) -> tuple[float | None, float | None]:
    offers = obj.get("offers")
    if isinstance(offers, dict):
        place = offers.get("availableAtOrFrom")
        if isinstance(place, dict):
            lat, lon = place.get("latitude"), place.get("longitude")
            if lat is not None and lon is not None:
                try:
                    return float(lat), float(lon)
                except (TypeError, ValueError):
                    pass
    geo = obj.get("geo")
    if isinstance(geo, dict):
        lat, lon = geo.get("latitude"), geo.get("longitude")
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (TypeError, ValueError):
                pass
    return None, None


def _address_from_listing(obj: dict) -> str:
    addr = obj.get("address")
    text = _format_address(addr)
    if text != "Not available":
        return text
    offers = obj.get("offers")
    if isinstance(offers, dict):
        place = offers.get("availableAtOrFrom")
        if isinstance(place, dict):
            pa = place.get("address")
            t = _format_address(pa)
            if t != "Not available":
                return t
            name = place.get("name")
            if isinstance(name, str) and name.strip():
                return _unescape_text(name)
    return "Not available"


def _info_from_residence(obj: dict) -> str:
    parts: list[str] = []
    if "numberOfBedrooms" in obj and obj["numberOfBedrooms"] is not None:
        parts.append(f"Bedrooms: {obj['numberOfBedrooms']}")
    if "numberOfBathroomsTotal" in obj and obj["numberOfBathroomsTotal"] is not None:
        parts.append(f"Bathrooms: {obj['numberOfBathroomsTotal']}")
    if "numberOfRooms" in obj and obj["numberOfRooms"] is not None:
        parts.append(f"Rooms: {obj['numberOfRooms']}")
    fs = obj.get("floorSize")
    if isinstance(fs, dict) and fs.get("value") is not None:
        unit = fs.get("unitCode") or ""
        parts.append(f"Size: {fs['value']} {unit}".strip())
    return " *** ".join(parts) if parts else "Not available"


def _pick_detail_listing_object(markup: bytes | str, page_url: str) -> dict | None:
    page_id = None
    m = re.search(r"/(\d+)/?(?:\?|$)", page_url)
    if m:
        page_id = m.group(1)

    candidates: list[dict] = []
    for obj in iter_json_ld_dicts(markup):
        if obj.get("@type") == "BreadcrumbList":
            continue
        if not isinstance(obj.get("offers"), dict):
            continue
        ou = obj.get("url")
        if isinstance(ou, str) and page_id and page_id in ou:
            return obj
        candidates.append(obj)

    for obj in candidates:
        ou = obj.get("url")
        if isinstance(ou, str) and page_url.rstrip("/") in ou.rstrip("/"):
            return obj
    return candidates[0] if candidates else None


def parse_listing_page(markup: bytes | str, page_url: str) -> dict[str, Any] | None:
    obj = _pick_detail_listing_object(markup, page_url)
    if not obj:
        return None
    title = _unescape_text(str(obj.get("name") or "No title"))
    description = obj.get("description")
    if isinstance(description, str):
        description = _unescape_text(description)
    else:
        description = "Not available"
    lat, lon = _lat_lon_from_listing(obj)
    canon = obj.get("url")
    if not isinstance(canon, str) or not canon.startswith("http"):
        canon = page_url
    return {
        "title": title,
        "url": canon,
        "address": _address_from_listing(obj),
        "latitude": lat,
        "longitude": lon,
        "price": _price_from_offers(obj.get("offers")),
        "info": _info_from_residence(obj),
        "description": description,
    }
