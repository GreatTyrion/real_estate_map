import json
import math
import numbers
import os
import time
from datetime import datetime
from queue import Queue
from typing import Any

import folium
import pandas as pd
from folium.plugins import MarkerCluster
from geopy.geocoders import ArcGIS

from get_kijiji_content import simple_get
from kijiji_jsonld import listing_urls_from_search, parse_listing_page

PART_1 = "https://www.kijiji.ca/b-house-for-sale/st-johns/"
PART_2 = (
    "c35l1700113?address=St.%20John%27s%2C%20NL&ll=47.5556097%2C-52.7452511"
    "&radius=50.0&view=list"
)

def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        print(f"Invalid integer for {name}={raw!r}; using default {default}")
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


MAX_PAGES = _env_int("REAL_ESTATE_MAP_MAX_PAGES", 13)
# 0 = no limit; use e.g. 3 for a quick smoke test
MAX_LISTINGS_PER_PAGE = _env_int("REAL_ESTATE_MAP_MAX_LISTINGS_PER_PAGE", 0)
# When False (default), JSON-LD coords from offers.availableAtOrFrom are ignored
# (they are often city/search-area pins); use geo + ArcGIS geocode instead.
TRUST_KIJIJI_OFFER_COORDS = _env_bool(
    "REAL_ESTATE_MAP_TRUST_KIJIJI_OFFER_COORDS", False
)

CSV_EXPORT_PATH = os.environ.get(
    "REAL_ESTATE_MAP_CSV_PATH", "kijiji_listings.csv"
).strip() or "kijiji_listings.csv"
GEOJSON_EXPORT_PATH = os.environ.get(
    "REAL_ESTATE_MAP_GEOJSON_PATH", "kijiji_listings.geojson"
).strip() or "kijiji_listings.geojson"


def search_page_url(num: int) -> str:
    if num == 1:
        return PART_1 + PART_2
    return f"{PART_1}page-{num}/{PART_2}"


def get_listing_urls(page_num: int) -> list[str]:
    url = search_page_url(page_num)
    body = simple_get(url)
    if not body:
        return []
    urls = listing_urls_from_search(body)
    if MAX_LISTINGS_PER_PAGE > 0:
        urls = urls[:MAX_LISTINGS_PER_PAGE]
    return urls


def web_scraper(page_num: int, data_queue: Queue, delay_sec: float = 2.0) -> int:
    urls = get_listing_urls(page_num)
    if not urls:
        print(f"No listing URLs on search page #{page_num}")
        return 0
    count = 0
    time.sleep(delay_sec)
    for item_url in urls:
        item_content = simple_get(item_url)
        if not item_content:
            continue
        parsed = parse_listing_page(
            item_content,
            item_url,
            trust_offer_place_coords=TRUST_KIJIJI_OFFER_COORDS,
        )
        if not parsed:
            print(f"Could not parse listing JSON-LD: {item_url}")
            continue
        data_queue.put(
            [
                parsed["title"],
                parsed["url"],
                parsed["address"],
                parsed["latitude"],
                parsed["longitude"],
                parsed["price"],
                parsed["info"],
                parsed["description"],
            ]
        )
        count += 1
        print(f"Completed scraping from {item_url}")
        time.sleep(delay_sec)
    print(f"Page #{page_num} scraped {count} ads")
    return count


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset=["address"])


def _cell_for_json(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (str, bool)):
        return v
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, numbers.Integral):
        return int(v)
    if isinstance(v, numbers.Real):
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    return str(v)


def save_listing_exports(
    df: pd.DataFrame, csv_path: str, geojson_path: str
) -> None:
    """Write full table to CSV and Point features to GeoJSON for analysis."""
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Saved {len(df)} rows to {csv_path}")

    features: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        lat, lon = row["latitude"], row["longitude"]
        try:
            if pd.isna(lat) or pd.isna(lon):
                continue
            flat, flon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        props = {col: _cell_for_json(row[col]) for col in df.columns}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [flon, flat]},
                "properties": props,
            }
        )

    collection: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
    }
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=2)
    print(
        f"Saved {len(features)} point features to {geojson_path} "
        f"(rows without coordinates skipped)"
    )


def geocode_missing_rows(kijiji_dict: dict, max_passes: int = 6) -> None:
    geocoder = ArcGIS()
    n = len(kijiji_dict["latitude"])
    for _ in range(max_passes):
        missing = [
            i
            for i in range(n)
            if kijiji_dict["latitude"][i] is None or kijiji_dict["longitude"][i] is None
        ]
        if not missing:
            break
        improved = False
        for i in missing:
            addr = kijiji_dict["address"][i]
            if not addr or addr == "Not available":
                continue
            try:
                loc = geocoder.geocode(addr, timeout=15)
                if loc:
                    kijiji_dict["latitude"][i] = loc.latitude
                    kijiji_dict["longitude"][i] = loc.longitude
                    improved = True
            except Exception:
                pass
            time.sleep(0.35)
        if not improved:
            break


if __name__ == "__main__":
    data_queue: Queue = Queue(maxsize=0)
    kijiji_dict: dict[str, list[Any]] = {
        "title": [],
        "url": [],
        "address": [],
        "latitude": [],
        "longitude": [],
        "price": [],
        "info": [],
        "description": [],
    }

    begin_time = datetime.now()
    for num in range(1, MAX_PAGES + 1):
        print(f"Working turtle {num} is about to scrape")
        web_scraper(num, data_queue)

    scrape_time = datetime.now() - begin_time
    print(f"Total scrape time: {scrape_time}")

    begin_time = datetime.now()
    print(f"Totally scrape {data_queue.qsize()} ads")
    while not data_queue.empty():
        data = data_queue.get()
        for index, key in enumerate(kijiji_dict):
            kijiji_dict[key].append(data[index])

    print("Begin to check and geocode address...")
    geocode_missing_rows(kijiji_dict)
    geocode_time = datetime.now() - begin_time
    print(f"Total geocode time: {geocode_time}")

    print("Web scraping has been completed.")
    df = pd.DataFrame(kijiji_dict)
    df = clean_df(df)

    save_listing_exports(df, CSV_EXPORT_PATH, GEOJSON_EXPORT_PATH)

    print("Housing map will be generated.")
    df_markers = df.dropna(subset=["latitude", "longitude"])
    if df_markers.empty:
        print(
            "No rows with coordinates; writing index.html centered on St. John's "
            "with no markers."
        )

    houseLocation = list(zip(df_markers["latitude"], df_markers["longitude"]))
    priceList = list(df_markers["price"])
    hrefList = list(df_markers["url"])
    houseInfo = list(df_markers["info"])
    titleList = list(df_markers["title"])
    houseDescription = list(df_markers["description"])

    popup_html = """
    %s<br>
    ######################<br>
    Price: %s<br>
    ######################<br>
    Information:<br>
    %s<br>
    ######################<br>
    Description:<br>
    %s<br>
    ######################<br>
    <a href="%s" target="_blank">Link to Kijiji</a>
    """

    def color_selector(price):
        # Folium.Icon has no "yellow"; beige is the closest built-in warm/light tone.
        try:
            price = float(price.replace("$", "").replace(",", ""))
            if price < 100000.0:
                return "green"
            if 100000.0 <= price < 200000.0:
                return "blue"
            if 200000.0 <= price < 300000.0:
                return "purple"
            if 300000.0 <= price < 400000.0:
                return "beige"
            if 400000.0 <= price < 500000.0:
                return "orange"
            if price >= 500000.0:
                return "red"
        except Exception:
            pass
        return "white"

    m = folium.Map(location=[47.5669, -52.7067], zoom_start=13)
    marker_cluster = MarkerCluster().add_to(m)
    update_time = datetime.now().strftime("%m/%d/%Y")
    fg1 = folium.FeatureGroup(
        name=f"Estate for sale from Kijiji updated on {update_time}."
    )
    def _escape_percent(s: Any) -> str:
        # popup_html uses "%" formatting; literal "%" in listing text must be doubled.
        return str(s).replace("%", "%%")

    for i in range(len(houseLocation)):
        iframe = folium.IFrame(
            html=popup_html
            % (
                _escape_percent(titleList[i]),
                _escape_percent(priceList[i]),
                _escape_percent(houseInfo[i]),
                _escape_percent(houseDescription[i]),
                _escape_percent(hrefList[i]),
            ),
            width=300,
            height=400,
        )
        folium.Marker(
            location=houseLocation[i],
            popup=folium.Popup(iframe),
            icon=folium.Icon(color=color_selector(priceList[i])),
        ).add_to(marker_cluster)

    m.add_child(fg1)
    m.add_child(folium.LayerControl())
    m.save("index.html")
    print("Map has been generated!")
