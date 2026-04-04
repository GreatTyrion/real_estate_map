# Development record

## Map tiles: OSM 403 when opening `index.html` locally (file://)

**Observed:** Leaflet/Folium default basemap loads tiles from OpenStreetMap’s public CDN. When the generated `index.html` is opened as a local file (`file://`), map tiles can fail with **HTTP 403** and copy such as “Access blocked” / “Referer is required” (see [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/)).

**Cause (typical):** Browsers often do not send a normal **`Referer`** for `file://` page loads, so tile requests do not satisfy the policy checks OSM applies.

**What still works:** Listing markers and popups may still render; only the raster basemap tiles are blocked.

**Mitigations (if we need them later):**

1. **Local HTTP server** — `python -m http.server` (or any static server), then open `http://localhost:.../index.html`.
2. **Host on GitHub Pages** (or similar) — page is served over `https://` with normal Referer behaviour.
3. **Change Folium basemap** — e.g. `folium.Map(..., tiles="CartoDB.Positron")` instead of the default OSM layer (Carto tiles are a separate provider; follow their terms).

**Status:** Default OSM tiles were restored in code after a brief experiment with CartoDB Positron; this note remains for future troubleshooting.
