# Real estate map (Kijiji, St. John’s area)

Scrapes **houses for sale** listings from Kijiji for the St. John’s, NL area, then builds an interactive **Folium** map (`index.html`).

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended)

## Setup

```bash
uv sync
```

To run the rental reference script under [`reference/scraper.py`](reference/scraper.py) (uses `loguru`):

```bash
uv sync --extra reference
```

## Run

```bash
uv run python web_turtle.py
```

### Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `REAL_ESTATE_MAP_MAX_PAGES` | `13` (see `web_turtle.py` if this drifts) | How many search result pages to walk |
| `REAL_ESTATE_MAP_MAX_LISTINGS_PER_PAGE` | `0` | Cap listings per page (`0` = no cap; use e.g. `3` for a quick test) |
| `REAL_ESTATE_MAP_TRUST_KIJIJI_OFFER_COORDS` | `0` (false) | If `1`, use JSON-LD `offers.availableAtOrFrom` lat/lon (often city-level); if `0`, skip them and use `geo` + geocode |
| `REAL_ESTATE_MAP_CSV_PATH` | `kijiji_listings.csv` | Path for the analysis CSV export |
| `REAL_ESTATE_MAP_GEOJSON_PATH` | `kijiji_listings.geojson` | Path for the GeoJSON export (`FeatureCollection` of Points) |

### Outputs

After each run, [`web_turtle.py`](web_turtle.py) writes (in order):

1. **`kijiji_listings.csv`** — All scraped rows after deduplication and geocoding (same columns as the in-memory table). `*.csv` is listed in [`.gitignore`](.gitignore), so exports stay local unless you change that.
2. **`kijiji_listings.geojson`** — Same attributes as properties; one **Point** per row that has both `latitude` and `longitude` (rows missing coords are omitted from GeoJSON only).
3. **`index.html`** — Folium map.

### Map marker colours (price bands)

Folium’s built-in marker palette has no literal `yellow`. For **$300k–$400k** the code uses **`beige`**, which is the closest available warm/light tone. Other bands: green / blue / purple / orange / red as defined in `web_turtle.py`.

## How coordinates are handled

Coordinates are **not** copied from [`reference/scraper.py`](reference/scraper.py); both pipelines use **Kijiji JSON-LD** and **geopy**, but they are not identical.

### What Kijiji actually exposes

On many listing pages, latitude and longitude under **`offers.availableAtOrFrom`** are **not a precise property survey point**. They are often a **search-area or city-level map pin** (for example centred on “St. John’s”) while the text address may say Mount Pearl, Torbay, etc. So using those numbers “as-is” can place markers in the wrong part of the metro area.

Top-level **`geo`** in JSON-LD is used when present and is **preferred** over `availableAtOrFrom` in [`kijiji_jsonld.py`](kijiji_jsonld.py).

### Default behaviour in this repo

By default (**`REAL_ESTATE_MAP_TRUST_KIJIJI_OFFER_COORDS` unset or `0`**), **`availableAtOrFrom` coordinates are ignored** so the map relies on **`geo`** (if any) and then **ArcGIS geocoding** of the listing address string—similar in spirit to the reference scraper, which fills coordinates from **`geo` on search JSON-LD when present**, otherwise **geocodes the address**. Set **`REAL_ESTATE_MAP_TRUST_KIJIJI_OFFER_COORDS=1`** only if you want the old behaviour (faster, fewer geocoder calls, but often **less accurate** pins).

Geocoding is still **approximate** (geocoder resolution, ambiguous addresses) but is usually **closer to the address text** than Kijiji’s regional offer pin.

[`web_turtle.py`](web_turtle.py) runs geocoding in **bounded passes** so a run cannot hang forever if geocoding fails.

### Why [`reference/scraper.py`](reference/scraper.py) can feel “more sufficient”

It is **richer as a script** (session setup, retries, logging, CSV export, summary stats, optional Folium/Google map paths), and for **rentals** it builds listings **only from search-result JSON-LD** without fetching every detail page—fewer HTTP requests. It does **not** magically read more precise GPS from the same JSON-LD: on search pages it only uses **`geo`** when Kijiji includes it, otherwise it **geocodes**. That often **avoids** the misleading `availableAtOrFrom` pin because that field is mainly populated on **detail** pages. The reference file also has **bugs and footguns** (e.g. inconsistent pagination URL keys, and placeholder/sample coordinates if geocoding fails), so it is reference material, not a drop-in “source of truth.”

## Project layout

| File | Role |
|------|------|
| [`web_turtle.py`](web_turtle.py) | Main entry: scrape → optional geocode → Folium → `index.html` |
| [`kijiji_jsonld.py`](kijiji_jsonld.py) | Parse Kijiji `application/ld+json` (search `ItemList`, detail listing objects) |
| [`get_kijiji_content.py`](get_kijiji_content.py) | HTTP session, headers, retries |
| [`reference/scraper.py`](reference/scraper.py) | Separate rental-focused scraper (reference / optional) |

## Pip (without uv)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python web_turtle.py
```

`uv.lock` is the authoritative resolved set when using `uv`.

## Known issues (map basemap tiles)

Opening **`index.html` via `file://`** can show **broken tiles** with messages like **“403 Access blocked / Referer is required”**. Folium’s default layer uses **OpenStreetMap**’s public tile servers, which enforce a [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) (including expectations around how requests are made). Local files often do not send an acceptable **`Referer`**, so tiles may fail while markers still appear.

**If this becomes a problem again**, options include:

- Serve the directory over HTTP (e.g. `python -m http.server 8765`) and open `http://localhost:8765/index.html`.
- Host the map on **GitHub Pages** or another normal `https://` origin (Referer behaviour is usually fine).
- In `web_turtle.py`, pass a different `tiles=` value to `folium.Map`, e.g. **`CartoDB.Positron`** (via xyzservices), which often works better for `file://` viewing.

Details are also recorded under [`development-records/DEVELOPMENT_RECORD_01.md`](development-records/DEVELOPMENT_RECORD_01.md). For a full repo overview, see [`development-records/DEVELOPMENT_DOCUMENT.md`](development-records/DEVELOPMENT_DOCUMENT.md).
