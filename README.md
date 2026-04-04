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

### Map marker colours (price bands)

Folium’s built-in marker palette has no literal `yellow`. For **$300k–$400k** the code uses **`beige`**, which is the closest available warm/light tone. Other bands: green / blue / purple / orange / red as defined in `web_turtle.py`.

## How coordinates are handled

Coordinates are **not** taken from `reference/scraper.py` directly. The flow is implemented in [`kijiji_jsonld.py`](kijiji_jsonld.py) and [`web_turtle.py`](web_turtle.py):

1. **Primary source — listing detail JSON-LD**  
   Each ad page includes Schema.org JSON-LD. When present, latitude and longitude are read from `offers.availableAtOrFrom` (Kijiji often puts approximate map coordinates there). This matches the same *idea* as the reference scraper (structured data first), but the house-for-sale pipeline uses the shared `kijiji_jsonld` helpers rather than copying `reference/scraper.py`.

2. **Fallback — geocoding**  
   If either coordinate is still missing, [`web_turtle.py`](web_turtle.py) calls **ArcGIS** via `geopy` on the listing address, with a bounded number of passes so a run cannot hang forever if geocoding fails.

Search-result JSON-LD usually does **not** include coordinates; a per-listing fetch is required for map placement unless geocoding succeeds.

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
