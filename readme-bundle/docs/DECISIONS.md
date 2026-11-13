# Decisions and deviations from SPEC.md

Each entry: date · phase · what changed · why.

## 2026-11-05 · phase 1

- **Repo root is `./`, not `last-safe-home/`.** The existing git repo (`d:\nasa`) is the project root;
  the §3 tree is laid out directly inside it.
- **pip fallback environment.** The dev machine has no conda, make or Docker, and only Python 3.13.
  Added `requirements.txt` mirroring `environment.yml`; local checks ran in a `.venv` (Python 3.13)
  instead of the conda `lsh` env (Python 3.11). The Makefile's `PY` variable can point at any
  interpreter (`make test PY=.venv/bin/python`). CI uses the conda env as specified.
- **`make` targets checked by running their commands directly**, because `make` is not installed here.
- **Extra pipeline command `show-config`** (`python -m pipeline.cli show-config --site <id>`) prints
  the parsed site file; used to check config loading.
- **Unbuilt steps exit with code 3** and name the phase that will build them, so `all` fails loudly
  rather than silently skipping.
- **`all` on a synthetic site runs `demo` then `publish`**, not the real-data steps.
- **Playwright added in phase 1** (spec: phase 4) with one smoke test (`web/e2e/smoke.spec.ts`) to check
  "blank map renders" automatically.
- **Web bundle is ~950 kB (265 kB gzip)**, mostly MapLibre; code-splitting is deferred to phase 8 (performance).
- **FastAPI's `ORJSONResponse` is deprecated** in the installed FastAPI; kept for now per §9 ("JSON via orjson"),
  to revisit in phase 3.
- **`koyra.yaml` name** set to "Koyra, Khulna" / "কয়রা, খুলনা" (the spec gives no name).
  `demo.yaml` AOI is a 0.1° box near 90.65E 22.65N; its content is entirely synthetic.
  Bangla strings still need a native-speaker check (§8).

## 2026-11-07 · phase 2

- **Local env is Python 3.12** (`py -3.12 -m venv .venv`) on this machine; 3.14 lacks wheels for parts of the
  geo stack. CI still uses the conda env (3.11).
- **`score` CLI step moved to phase 6.** Phase 2 builds the score *module* (`score.py`); the `score` step needs
  real bank lines, transects and context data. For the demo, `demo.py` plays the role of `score`/`validate`
  and writes `stats.json` and `validation.json` itself.
- **Score rounding is half-up** (`floor(x + 0.5)`), not Python/numpy round-half-to-even, so the raster and
  scalar point queries round identically.
- **Unknown or non-positive retreat rate → T = +inf, H_E = 0** (the §8 formula only defines R > 0).
- **`years_static` caps +inf at 1000 years** so the COG holds no infinities (the UI shows "over 50 years").
- **`transects.py` core built early** (baseline, cast, first intersection, OLS rate, trimming) because the demo
  uses it; the `transects` step that reads real bank lines is still phase 6.
- **Transect direction uses a smoothed tangent** (chord over ±1 km along the baseline). Inland-buffering the
  land polygon (§7.6.1) turns each small bank bulge into a circular arc whose exact normals all converge on
  one bank point; the smoothed tangent keeps neighbouring transects near-parallel (as DSAS does).
- **Transect geometry is trimmed for display** to 100 m past the farthest bank crossing and clipped to the AOI
  (rates still use the full `transect_length_m`). Transects also carry `dist_today_m`, `bank_lon`, `bank_lat`
  (crossing with today's bank) so the API can find the nearest transect exactly as the score raster did.
- **Extra product `cog/<site>_population_static.tif`** (people per analysis-grid pixel). §7.9 resamples
  WorldPop to the analysis grid but §5 gives it no file name; polygon stats need it.
- **`layers.json` additions:** `landwater` (`{year}` pattern, needed by compare mode §10.6), `sar_hv`, `floodveg`,
  `mndwi`, `coherence`, `distance`, `years`, `population`, and `bank_date` (date of today's bank line).
  In patterns `{date}` is the file key `YYYYMMDD`; `nisar_dates` stay ISO. Custom colormaps: `water`, `floodveg`,
  `custom-score`.
- **`publish` always rewrites `layers.json`** (it is cheap and derived only from files on disk) instead of
  skipping when it exists; it refuses to write a manifest that points at a missing file.
- **Step summaries** are written to `data/processed/<site>/summaries/<step>.json`.
- **Bank line properties:** Landsat lines have `date: null`; `nisar-median3` lines carry the window's last
  date plus `window: [first, last]`.
- **Union stats are flat properties** (`buildings_low`, `people_high`, …, `name_en`, `name_bn`) because MapLibre
  stringifies nested GeoJSON properties.
- **Demo site config:** `baseline_inset_m: 2500`, `transect_length_m: 4500` (the synthetic river migrates up to
  ~1.9 km since 1988, more than the 1500 m default inset). Demo NISAR dates follow a 12-day repeat from
  2026-06-17, skipping the instrument gap: 10 passes, last 2026-10-15. Demo buildings use 4.4 people/building.

## 2026-11-07 · phase 3

- **Dropped `ORJSONResponse`.** It is deprecated in the installed FastAPI (0.162), which now serialises
  responses through pydantic response models directly (fast, no extra class). Errors use `JSONResponse`.
- **Static analysis rasters are held in memory, not as open dataset handles.** `store.py` loads distance,
  flood frequency, motion, population, score, years and the Landsat land/water masks as numpy arrays at
  startup (a few MB per site), which is faster for point/polygon queries and avoids sharing rasterio handles
  across FastAPI's worker threads. Tiles open the COG per request with rio-tiler (local files, ~ms).
- **`create_app(settings)` factory** in `api/app/main.py` so tests run the API against a temp demo data dir;
  `app = create_app()` is still the uvicorn entry point. A root `conftest.py` generates the demo site once per
  test session for both pipeline and API tests.
- **`/health` lists the sites actually loaded** (configured in `SITES` *and* with a `layers.json`), not every
  configured site; `/sites` likewise.
- **Point query "outside the AOI"** = outside the AOI polygon *or* on a nodata pixel of the latest NISAR water
  mask (pixel centres just outside the polygon at the edge). Inside with no land distance = `in_river`.
  The nearest transect is found exactly as the score raster does (KD-tree on today's bank crossing,
  transects with a rate only). Extra field `data.bank_date`.
- **`years_until_river.over_50`** is true when the central estimate is over 50 years or infinite; infinite
  values are returned as `null`.
- **Tiles:** `date` selects the file for `{date}` layers (ISO date) and `{year}` layers (`date=1988` or
  `year=1988`); missing → latest. Static layers ignore it. `date` is capped at 10 characters (422 beyond).
  Categorical layers (water, floodveg, score) use nearest resampling, continuous ones bilinear. The score
  colormap is an interval map on the raw 0–100 value. Every response carries a `Server-Timing` header.
- **`POST /scenes` answers 501 `not_implemented`** until phase 7 (in the standard error shape).
- **Polygon stats:** pixels are those whose centre lies inside the polygon (for a polygon smaller than one
  pixel, the pixel under it). Invalid self-intersecting polygons are repaired with `make_valid`; non-polygon
  bodies get 422 `invalid_geometry`.
- **Demo transects starting within one pixel of the AOI edge are dropped** (a 6 m stub on the edge).

## 2026-11-07 · phase 4

- **No router library yet.** The app is a single page at `/`; the Method/About links point at `/method` and
  `/about`, which are built in phase 7 together with `/report`.
- **Not in phase 4 (later phases):** compare mode and the "Print report" buttons (phase 7, with `/report`);
  the mobile bottom-sheet layout (phase 8). Below 1024 px the sidebar overlays the map and the drawer is
  full-width, which is usable but not the final mobile design.
- **Extra URL parameter `pt=lon,lat`** for the inspected point, so "Copy link" reopens the point card.
  `lat/lon/z` stay the map centre as in §10.1. An empty `layers=` means "all layers off".
- **No `@turf/turf` yet.** Areas come from the API; union label positions use a small in-repo helper
  (`web/src/map/geometry.ts`). Add turf when a phase needs real client-side geometry.
- **Union names are HTML markers, not MapLibre symbol labels.** MapLibre's glyph renderer does not shape
  Bangla script correctly; the browser does. Clicking a union label opens the union's statistics in the
  drawer (from the unions GeoJSON properties). Clicks elsewhere on the map are point queries.
- **Polygon drawing:** Terra Draw polygon mode; double-click (or clicking the first/last point) finishes.
  After finishing, the tool switches back to Inspect and the polygon stays on the map until "Clear" or the
  next drawing. Choosing Draw closes an open point card so the drawer does not cover the drawing area.
- **Scene list in the polygon panel** calls `POST /scenes` already and shows "not available in this build
  yet" for the 501 answer until phase 7.
- **Time slider** is a custom ARIA slider (ticks spaced by real time so the July–August instrument gap
  shows as a shaded span). Arrow keys work on the slider and anywhere outside form fields and the map
  canvas (the map keeps its own arrow-key panning).
- **Playwright runs against `uvicorn` + `vite preview` started by `playwright.config.ts`**, not
  `docker compose up` — the Docker setup arrives in phase 9. The API is started with `SITES=demo`.
  CI runs the e2e job on pushes to `main`.
- **`"The Last Safe Home"` stays in English in both languages** (it is the app's name); the tagline and
  everything else is translated. All Bangla strings still need a native-speaker check before release (§8).
- **Bundle:** maplibre + terra-draw are split into their own chunk (`vite.config.ts`); the remaining size
  work is phase 8.

## 2026-11-07 · phase 5

- **NISAR track for Manpura: 69 ascending (frame 13)**, chosen by the user from the inventory. Both track 69
  and track 91 descending had 10 GCOV passes since 2026-06-17; track 69 has HH+HV on all 10, track 91 has HH on
  only 6 (4 passes are VV/VH only). Set in `config/sites/manpura.yaml`.
- **NISAR data are fetched as AOI subsets, not whole files** (the user's choice; full files are ~6 GB each,
  62 GB for track 69). `fetch-nisar` opens each remote `.h5` through HTTP range requests (`RangeFile`) and copies
  the AOI window (+300 m) of `HHHH`, `HVHV`, `mask`, `numberOfLooks`, the coordinate vectors, `projection` and the
  small identification datasets into `raw/<site>/nisar/gcov/<granule>_aoi.h5`, keeping the product's group layout.
  Real cost for Manpura (track 69, 10 dates): ~420 MB read per date (the product's compressed chunks are larger
  than the AOI window), 4.2 GB read in total, 594 MB kept on disk, ~3.5 min per date.
  `--full` still downloads whole products, refusing over 20 GB (or over free disk) unless `--confirm-large`.
  GUNW is fetched in phase 6 (`motion`).
- **Track choice counts usable HH passes**, not all GCOV granules: the water mask needs HH, and a granule must cover
  ≥ 90 % of the AOI. One GCOV granule per date (best AOI cover, full frame, smaller file). With `track: null` and
  more than one track at ≥ 6 passes, `fetch-nisar` writes the inventory and stops (exit 4) until a track is set.
- **inventory.csv has three extra columns**: `full_frame`, `aoi_cover` (fraction of the AOI inside the footprint)
  and `selected`.
- **Earthdata account setup:** ASF refuses NISAR downloads until (1) the account's *Study Area* profile field is
  filled in and (2) the ASF data application is authorized once (`urs.earthdata.nasa.gov/approve_app?...`); the
  pipeline stops with the matching instruction and link instead of a traceback.
- **GCOV reading:** HDF5 paths follow the spec; if the GCOV grid group is elsewhere the reader searches for the group
  holding `xCoordinates` (trust the file). EPSG from `projection` attribute `epsg_code` (or its value).
  `mask` is read as 255 = fill, 0 = invalid, others valid; if that would discard > 99 % of finite pixels the mask
  is ignored with a warning. **Verified on the real Manpura files (product version 1.0.11):** the spec's group
  paths are right; `projection` carries `epsg_code` = 32646 (same as the site); posting is 10 m (40 MHz mode);
  the product describes `mask` as "subswath number of valid samples; 0 = partially focused/invalid; 255 = outside
  the acquisition" — matching the reading above. Manpura is fully valid on all 10 dates. HH median over the AOI
  ≈ −17.5 dB; open water ≈ −19 to −24 dB (wind roughening makes it brighter than calm water).
  Dates with no HH layer (VV-only) are skipped with a note in the step summary.
- **GCOV grid:** all dates are resampled (bilinear, on linear power, then dB) onto one site grid at the product's
  native posting in the site UTM CRS, clipped to the AOI polygon, so the water masks of all dates stack directly.
- **Landsat:** composites are loaded straight onto the site's 30 m grid (`odc.stac.load(geobox=...)`), up to the
  12 least cloudy scenes per year, `fill` bit (0) masked as well as dilated cloud, cloud and shadow. "Newest
  available" treats Landsat 8 and 9 as one group. For Manpura, Jan–Mar 2003 had no Landsat 5 scene under 40 %
  cloud on Planetary Computer, so 2003 uses Landsat 7 (SLC-on, before the May 2003 failure); 2013 has only
  Landsat 7 SLC-off scenes in Jan–Mar (Landsat 8 starts in April 2013) — the median of 12 scenes fills the stripes
  (clear AOI fraction 1.0).
- **Context:** Overpass responses are cached raw; buildings are stored as centre points with `kind`
  (`building`, `school`, `hospital`, `place_of_worship`). Roads are also written to `vector/<site>_roads.geojson`
  (not in §5; not yet used by the app). WorldPop's server refuses range reads, so the national 100 m file (2025
  R2025A constrained, 55 MB; falls back to 2020 constrained) is downloaded once to `raw/<site>/context/` and clipped.
  It is resampled to the 30 m analysis grid with GDAL `sum` and written as `cog/<site>_population_static.tif`
  (totals match: 241,018 → 241,022 people in the Manpura AOI). Unions come from geoBoundaries ADM4 (simplified
  geometry), clipped to the AOI. **geoBoundaries has no Bangla names**: `name_bn` repeats the English name until
  someone supplies the Bangla names.
- **New module `pipeline/lsh/grid.py`** (`site_grid`) shared by gcov, landsat and context.

## 2026-11-08 · phase 6

- **SAR water masks follow the spec (Otsu on smoothed HH dB).** Manpura's monsoon masks also mark flooded paddy and
  wet mudflats as water: at L-band they are as dark as the river (HH ≈ −18 dB, HV ≈ −24 dB). Otsu thresholds
  −11.7 … −12.9 dB; water fraction 61–80 % of the AOI vs ~54 % in the dry-season Landsat mask.
- **The spec's bimodality test is weak:** Otsu's between-class/total variance ratio for a single Gaussian is 2/π
  ≈ 0.64, above the 0.5 cut-off, so the fallback rarely triggers. Kept as specified (Manpura dates: 0.83–0.90).
- **Flooded vegetation:** there is no dry-season NISAR pass (all are Jun–Oct), so the reference is the per-pixel
  median HH over all 2026 passes; flag = HH > median + 3 dB on non-water pixels. In October it flags 17 % of the
  AOI — maturing rice in standing water (double bounce).
- **Bank lines use a river corridor for NISAR:** NISAR water counts as river only within 300 m of the latest
  dry-season Landsat river (`banklines.CORRIDOR_M`); floodplain water outside it is flooding, not river. Landsat
  cloud gaps (255) take the value of the nearest year with data. Land specks < 0.02 km² are dropped; land is
  opened by half a pixel and simplified 15 m. Land polygons (UTM) go to `work/land_utm.geojson` for later steps.
- **NISAR banks sit ~80 m inland of the dry-season Landsat banks on average** (October river stage, wet
  mudflats). With the latest NISAR median-of-3 point in a 38-year OLS this biases rates by < 1 m/yr.
- **Transects:** the baseline land is the 1988 land with creeks narrower than 400 m closed and holes dropped
  (a 1988 creek through Manpura otherwise produced fans of transects across the island); baseline parts within
  inset + 300 m of the AOI edge are skipped. Bank distances are **signed**: when the bank has retreated past the
  baseline (start in water) the distance is measured backwards and is negative. Crossings use an STRtree of bank
  segments (real coastlines have tens of thousands of vertices).
- **Motion:** GUNW AOI subsets (`unwrappedPhase`, `coherenceMagnitude`, `connectedComponents`,
  `ionospherePhaseScreen`, `mask`; 80 m) are fetched by `fetch-nisar`. Verified on the real files: paths match
  the spec; the 7 HH pairs of track 69 form a 12-day chain 2026-07-12 → 10-16 (96 days). The product states no
  sign convention; from ISCE3's reference × conj(secondary) and exp(−j4πR/λ), positive phase = range increase,
  so the spec's d = −λ/4π·φ (positive = toward the satellite) is used unchanged. The ionosphere phase screen is
  subtracted (the "ionospheric correction applied" flags refer to geocoding). Pixels need coherence ≥ 0.4,
  connected component > 0 and a valid GUNW mask (subswath digits ≠ 0, no RSLC anomaly bits). Missing pairs in
  the chain are filled by scaling with covered time. **Result: coherent land 0.2 % (mean land coherence 0.34)
  → `motion_usable = false`**; the score uses erosion 0.667 / flood 0.333 per §8 and the UI hides the layer.
- **Score step lives in `pipeline/lsh/scoring.py`** (`score.py` stays the shared formula module). Today's land
  = the latest NISAR median-of-3 land polygon on the 30 m grid; distance ignores the AOI box edge. Buildings
  standing in today's river count as distance 0. Union stats are written into the unions GeoJSON; stats.json adds
  `bank_source`. Pixels on chars with no transect of their own take the nearest transect's rate (spec rule) —
  raised with the user.
- **Validate:** area check uses the island = land piece (creeks closed) overlapping the four Manpura upazila
  unions (`validation.island_unions` in the site file); compared with the closest year and with the published
  decline interpolated to each Landsat year. `validation.json` keeps `status: not_validated` (no labelled points
  yet) and adds `area_check` and `sentinel2_check`. Sentinel-2 comes from Planetary Computer, with Element84
  Earth Search as a fallback when PC is unreachable. `validate --make-points` wrote 200 points to label.
- **Bug fixed during the phase:** `io.read_raster` turns mask nodata (255) into NaN, so `== 255` tests saw no
  nodata; masks are now read with the new `io.read_mask` (bank lines, flood).
- **UI:** the site summary shows land *lost to the river* and land *gained* separately (Manpura's AOI gained
  160.7 km² and lost 88.1 km² since 1988 — net growth would have shown as a negative "land lost").
- **Sentinel-2 sanity check measures the river outline, not every water/land edge.** The first version compared
  all NDWI shoreline pixels (field puddles, flooded paddy edges, cloud edges) and got a median of 15 px. The check
  now (1) uses MNDWI > 0 (green/SWIR, the index the Landsat masks use; NDWI calls turbid water and wet mud land),
  (2) extracts the river from both masks exactly as `banklines` does (dry-season corridor + connected components),
  (3) uses the Sentinel-2 day nearest the NISAR pass with ≥ 80 % clear AOI, (4) drops pixels within 3 px of
  cloud, and (5) reports both the single pass and the median-of-3 map (today's bank).
  **Result for Manpura (NISAR 2026-10-16 vs S2 2026-10-17): river IoU 0.93, median outline distance 5.4 px
  (54 m), 34 % of outline pixels within 2 px.** This still misses the spec's "~2 px", and the miss is one-sided:
  97.5 % of disagreeing river pixels are NISAR-water / S2-land — wet intertidal mud on the char edges, which is
  as dark as water at L-band, and a different tide (NISAR 05:21 local, S2 10:28 local; the Meghna estuary has a
  2–4 m tidal range over very flat banks). Thresholds were **not** tuned to the validation scene. Effect: today's
  bank sits ~50–80 m inland, so distances to the bank are short by that much and "years until the river" is on the
  cautious (earlier) side; rates are dominated by the 38-year Landsat record (< 1 m/yr bias). The user was told
  and asked to continue; the limitation is stated on the Method page.
- **New helpers `banklines.landsat_river` and `banklines.corridor_mask`** (shared by `banklines` and `validate`).

## 2026-11-08 · phase 7

- **`POST /scenes`**: asf_search server-side, `PR` products only (§16), one search per product level with
  `maxResults=100`, merged, de-duplicated, newest first, capped at 100, cached 1 h (in-process, max 256 entries)
  keyed by a SHA-256 of (simplified WKT, products, start, end). The polygon is simplified to 1e-4° and oriented
  counter-clockwise first (ASF limits WKT size and otherwise "repairs" the winding). `url_asf` is an ASF Vertex
  list-search link for the granule (the user logs in there to download). `track` is a string (the API returns
  what ASF returns). CMR sometimes returns short pages; asf_search then marks the result incomplete and we **do
  not cache** it. ASF failure → 502 `search_failed`; bad geometry/products/dates → 422. Tests mock
  `asf_search.search`.
- **Router: History API, no library** (`web/src/router.tsx`): `/`, `/method`, `/about`, `/report`; paths are
  relative to Vite's `BASE_URL`. Method/About/Report are lazy chunks so the map bundle did not grow. The map
  view is kept in the store, so "Back to the map" returns to the same view. Static hosting needs the SPA
  fallback (phase 9).
- **Compare mode** uses `@maplibre/maplibre-gl-compare@0.5.0` (its `index.js` needs Node's `events`, so the
  `events@3.3.0` browser package is a dependency). The right side follows the **time slider** (the latest pass
  by default, as the spec says); the left side is the earliest Landsat year (`landwater` + that year's bank line).
  Both sides draw bank lines white on a dark casing. The swipe handle is focusable and moves with arrow keys;
  Esc and "Exit compare" leave the mode; Reset view works in compare mode; choosing Inspect/Draw leaves it.
  `mode=compare` is in the URL.
- **Report** (`/report`): the polygon is encoded as its outer ring in JSON, 5 decimals, closing point dropped,
  ≤ 500 vertices. The map is MapLibre with `preserveDrawingBuffer` and is swapped for a PNG on the first `idle`
  after the data layers load (20 s fallback; if the canvas is tainted the live map stays and still prints).
  It shows score, water on the latest pass and today's bank (`nisar-median3`). The point/polygon numbers reuse the
  card/panel components (`PointSummary`, `PolygonSummary`), so they cannot differ. "Print report" opens it in a
  new tab; printing is the browser's (A4, 12 mm margins).
- **Method page**: `docs/METHOD.md` is now written (phase 9 may polish it) and has a Bangla version
  `docs/METHOD.bn.md`, rendered with `marked` (our own text, compiled in). Live validation numbers (status,
  accuracy/confusion matrix when labelled, area check, Sentinel-2 river-outline check), limitations (site-aware:
  synthetic, motion not usable with the coherent-land %) and data credits are React sections with i18n strings.
  Vite's dev server is allowed to read `..` for the `?raw` import; the phase 9 Docker build context must include
  `docs/`.
- **About page**: team names come from `TEAM` in `web/src/config.ts`, **empty for now** (a generic line is shown
  until the team fills it in); repository link `https://github.com/AriyaArKa/nasa`.
- **Credits** add Sentinel-2 ("contains modified Copernicus Sentinel data 2026", used for validation) and the
  Esri basemap; the NISAR/Landsat wording is §16's.
- **Manual Manpura check is a gated Playwright spec** (`web/e2e/manpura.manual.spec.ts`, runs with
  `E2E_MANPURA=1` against an API with `SITES=manpura,...`); it also checks on-screen numbers against `stats.json`.
- **Working copies normalised to LF** (the index already stored LF; `.gitattributes` is `* text=auto`).

## 2026-11-08 · phase 8

- **Mobile (< 1024 px)**: the sidebar becomes a bottom sheet above the time slider with two tabs (Layers ·
  Site summary; tap the open tab to fold it, max 45 vh); the drawer is full screen; Method/About sit in a "⋮" menu
  below 768 px; the map's +/− buttons are hidden (pinch zoom; they sat under the tool buttons); the slider's gap
  label is hidden below 640 px (the shaded span and its tooltip stay). The sidebar toggle shows on desktop only.
- **Loading/error states**: static boot screen in `index.html` (paints before any JS); "Loading map data…" chip
  while a site's manifest loads; banners for offline, API down (with Try again; the site-data banner is suppressed
  then), site data failing (Try again); site summary error; a one-time "some map layers could not load" notice
  when our tiles/vectors fail; a React error boundary with a Reload button; skip link to the map.
- **Accessibility**: site `<select>` has an `aria-label` (its visible label is hidden on phones); union labels
  are ≥ 24 px tall and labels that would overlap a bigger union's label are hidden (and leave the tab order)
  until there is room; the drawer moves focus to its Close button when opened from the keyboard and returns it
  on close (map clicks keep focus on the map); sheet tabs use the ARIA tab pattern; 44 px tab targets.
- **Performance**:
  - The API serves vectors compacted (5-decimal coordinates ≈ 1 m, no whitespace) — the files on disk keep full
    precision and the queries use them. New `?source=` filter on `vectors/banklines` (subset of
    `landsat,nisar,nisar-median3`, else 422): the map loads `landsat,nisar`, the report `nisar-median3`.
    Manpura bank lines: 808 → 478 KiB gzip.
  - Bank lines and unions load after the first map frame with tiles; Buildings and Transects (off by default,
    3 MB for Manpura's buildings) load the first time they are switched on.
  - MapView/CompareView and Terra Draw are lazy chunks (map code no longer blocks the page shell; drawing
    loads when Draw is first picked — the hint appears once it is ready).
  - No tile cross-fades (`fadeDuration: 0`, `raster-fade-duration: 0`): far fewer frames drawn while tiles
    arrive. Map `pixelRatio` capped at 1.5. Google Fonts CSS no longer render-blocking. Favicon added.
    Source maps are built (`build.sourcemap`).
- **Lighthouse (local, Lighthouse 12.8.2, headless Chromium without a GPU, Manpura)**: mobile, simulated
  throttling: performance 49–69 (median ~61, very noisy), accessibility 100, best practices 100; mobile with
  devtools throttling: 68–69, **FCP/LCP 1.4 s** (target "first load < 3 s on Fast 4G" met); desktop: 90 / 97→
  100 after the label fix / 100. Method page (mobile): 88 / 100 / 100. **The mobile ≥ 80 performance target is
  not met locally**: the remaining blocking time (~1.2–2 s) is MapLibre drawing frames with *software* WebGL
  (SwiftShader) as tiles arrive, which a phone's GPU does in milliseconds. It must be re-measured on the deployed
  site (phase 9; the spec's acceptance is on the deployed site).
- Playwright: `e2e/mobile.spec.ts` (phone layout; API-down banner); CI retries a failed test once (the full flow
  calls the real ASF search and OSM tiles).

## 2026-11-08 · phase 9

- **Deploy configs only; not deployed** (the user's choice): deploying needs the team's accounts and makes the app
  public. Ready: `api/Dockerfile`, `web/Dockerfile` + `web/nginx.conf`, `docker-compose.yml`, `render.yaml`
  (API), `vercel.json` (web), `.github/workflows/pages.yml` (GitHub Pages alternative, manual trigger), README
  "Deploying". The "public URL works from a phone" check is therefore open until someone deploys.
- **Docker is not installed on the dev machine**, so the images were not built here. Instead: (1) the API's
  runtime dependency set (`api/requirements.txt`, pinned to the tested versions) was installed in a clean
  virtualenv and served the packed Manpura + demo data (health, point, polygon, scenes, tiles all OK; 258 MB
  resident); (2) a new CI job `docker` builds both images on every push, starts the API image with the demo data
  baked in and checks `/health` and `/point`.
- **API image**: python:3.11-slim + `api/requirements.txt` (rasterio/pyproj/shapely wheels bundle GDAL/PROJ/GEOS),
  only `config/`, `pipeline/lsh/`, `api/app/`. Data comes from the build context's `data/deploy/processed` (read
  through a BuildKit bind mount, so it is not stored twice) **or** from `DATA_URL` (a `.tar.gz` downloaded at
  build time — Render builds from git, where `data/` is not committed). The build fails if the data is over
  1.5 GB (SPEC §12). Listens on `$PORT`, runs as a non-root user, has a Docker health check.
- **New `pipeline.lsh.pack`** (`make pack`): the deploy copy of the data — only the files `layers.json` points at,
  plus `stats.json` / `validation.json` (no `work/`, summaries, logs); `sar_hh` rounded to 0.1 dB and stored with
  a floating-point predictor; `sar_hv` left out (no HV layer in the app; `--keep-hv` keeps it). Size check:
  warning > 1 GB, error > 1.5 GB. Manpura 799 MB → 296 MB. The local `data/processed` is never changed.
- **Web image**: node:20 build (context = repo root because `/method` imports `docs/`), nginx with SPA fallback,
  long cache for hashed assets, `/api/` proxied to the `api` service, so `VITE_API_URL=/api/v1` works. Compose
  serves the app on http://localhost:8080 and mounts `./data/processed` read-only into the API.
- **`VITE_BASE`** sets Vite's `base` for sub-path hosting (GitHub Pages `/<repo>/`); the router, assets and the
  report's "open this view" link follow it.
- **METHOD.md** (written in phase 7) gains a "Data and references" section (both languages).
- **README** rewritten: quick start (make, Docker, pip/Windows), real data, adding a site, deploying, layout,
  credits, limitations.

## 2026-11-08 · phase 10

### Second site: Koyra, Khulna

- **NISAR track 170 ascending (frame 13)**, chosen by the user from the inventory: 10 HH+HV GCOV passes
  2026-06-25 → 11-04, 100 % AOI cover, 9 HH GUNW pairs. Track 19 descending also had 10 HH passes with full cover
  but only 4 GUNW pairs; track 91 covers 39–79 % of the AOI. Fetched as AOI subsets like Manpura.
- **Two product versions of one interferogram**: ASF lists the GUNW pair 2026-08-24 → 09-05 as `…_J_001` and
  `…_J_002` (a reprocessing). The motion step counted it twice, which broke the 12-day chain. Fixed in two places:
  `fetch-nisar` selects only the newest version per date pair (`nisar.latest_versions`), and `motion` ignores
  older versions already on disk (`nisar.pair_key`). Koyra: 8-pair chain, 108 days.
- **Enclosed shrimp ponds are not river (new per-site option `analysis.river_min_km2`).** SPEC §7.5 counts water
  as river if it touches the AOI edge *or* is larger than 1 km². Koyra's polders hold large enclosed aquaculture
  ponds (ghers): in the 2026 Landsat map 30 enclosed water bodies of 1–4.4 km² (57 km²) became "river", with
  bank lines and high scores far inland. `river_min_km2: null` (Koyra) keeps only edge-connected water; the
  default stays 1.0 as specified (Manpura, demo — the rule makes no difference there: identical river areas).
  Koyra, before → after: land eroded since 1988 141 → 80.5 km²; high + severe area 165 → 76 km²; buildings within
  500 m of the bank 29 898 → 22 077.
- **Koyra sanity checks (phase 6 list)**: 1261/1261 transects with a rate, −15…+81 m/yr; score in all four
  classes, river NaN; Sentinel-2 river outline vs NISAR 2026-11-04: median 1.4 px (**within 2 px — passes**,
  unlike Manpura); no published land areas for an area check (`validation.published_area_km2` not set).
- **Koyra motion is "usable" by the spec's rule but looks noisy** (reported to the user, not changed — the
  score weights need the user's approval, §16): 53.6 % of the land coherent (rule: ≥ 30 %), so the motion layer
  is shown and weighted 0.1. But the season displacement spans −50…+68 mm (5th–95th percentile) in 108 days, with
  smooth large-scale patterns over the Sundarbans forest — more like tropospheric/unwrapping noise accumulated
  over 8 pairs than ground motion. At most it adds 10 points to a score (H_G = 1 from |M| ≥ 30 mm).
- Koyra packs to 416 MB (all three sites 724 MB, under the 1 GB the spec expects).

### Static fallback

- **`python -m api.static_export`** (`make static`) writes API-shaped static files rendered by the API's own code
  (`render_tile`, `point_query`): `sites.json`, per-site `layers.json` (with a `static` block: tile zooms and
  grid spacing) / `stats.json` / `validation.json`, compact vectors (+ the two bank-line source variants),
  PNG tiles z 8–14 for score, flood frequency, motion (if usable), water on every NISAR date and the earliest
  Landsat water (compare), and **`points.json`**: the point answer at every cell centre of a ~100 m lon/lat grid
  (coarser if a site would pass 120 000 cells), stored column-wise. Manpura: 86 165 cells, 6.5 MB; tiles ~3 800.
- **The web app reads them when built with `VITE_STATIC_URL`** (`api/staticSource.ts`): same client interface;
  clicks answer with the containing grid cell (the card says "precomputed for a 100 m square"); polygon stats and
  scene search fail with `static_unavailable` and the panel says the live server is needed; a banner marks the
  offline edition; tile sources stop at the pre-rendered zoom (MapLibre over-zooms); missing tiles (no data
  there) are 404s and no longer count as errors.
- **Not pre-rendered**: the radar backscatter (`sar_hh`, ~300 MB of tiles per site) — left out of the static
  manifest, so the layer is not offered.
- Tests: `api/tests/test_static_export.py` (files, and grid answers equal the API's at cell centres),
  `web/src/api/staticSource.test.ts`; a gated Playwright spec `e2e/static.manual.spec.ts` (passes against a static
  build with **no API running** — it also asserts that no request goes to `/api/v1`).
- The map now logs which source failed (`console.warn("map data error", …)`) when it shows the
  "some map layers could not load" notice (seen once on Koyra right after an API restart, not reproducible).

## 2026-11-08 · screenshots for the README

- `docs/screenshots/` (16 PNGs, real Manpura/Koyra data + the demo site) made by the gated Playwright spec
  `web/e2e/screenshots.manual.spec.ts`; the README describes each feature and its real-life use.
- Two bugs found while taking them, both fixed:
  - **Compare panes had zero height** since phase 8 made the map code lazy: `maplibre-gl.css` now loads after
    Tailwind and its `.maplibregl-map { position: relative }` overrode the panes' `absolute inset-0`. The panes
    (and the report's live map box) now set their position inline. The e2e test now checks the panes' height.
  - **"Some map layers could not load" appeared on normal page loads**: setting the default date re-set the
    water/radar tile URLs to the same value, which cancelled in-flight tiles, and MapLibre reports cancels as
    `AbortError`. Tiles are now re-set only when the date changes, and aborted requests are not counted as errors.

## 2026-11-12 · home page; the map moves to /map

- **Deviation from SPEC §10.1 ("/" = the map app, no marketing pages):** the team asked for a home page. `/` is now
  a landing page (`web/src/pages/HomePage.tsx`): title and a short description, a big "Start exploring the map"
  button, life on the river bank, how it works in four steps, six screenshots, the data sources and how each is
  used, and the team with roles. English and Bangla strings live under `home.*` in `en.json` / `bn.json`.
- **The map is at `/map`.** Old map links that point at the root with map parameters (`/?site=…`, `lat`, `lon`, `z`,
  `layers`, `date`, `pt`, `mode`) are rewritten to `/map?…` at start-up (`legacyMapPath` in `router.tsx`), so shared
  links, the README URLs and the e2e specs keep working. `/?lang=bn` (no map parameters) stays on the home page.
  Unknown paths now show the home page instead of the map. "Back to the map" links and the report's links go to
  `/map`; the app name in the top bar and a "Home" item lead back to `/`.
- **The map code now loads on demand** (`lazy(() => import("./App"))`) so the home page paints without MapLibre;
  the home page prefetches it 1.5 s after loading so "Start" opens at once.
- **Artwork:** the hero is an original inline SVG (`pages/home/RiverScene.tsx`): sunrise over a river, a house on
  a crumbling bank, a nouka, a child's kite, and a dashed "bank in 1988" line out in the water. Flag green
  (#006a4e) and red (#f42a41), the app's river blue and the four risk-class colours. No downloaded photos.
  Motion (waves, boat, kite) stops under `prefers-reduced-motion`.
- **Screenshots** on the home page are 960 px WebP copies of `docs/screenshots/` in `web/public/home/` (~515 KB
  for six).
- **Live numbers:** the "Manpura, measured from space" band reads `/sites/manpura/stats` (works in the static
  edition too); it shows placeholders until the answer arrives.
- Tests: `web/src/router.test.ts` (routes, legacy redirect); `reportUrl.test.ts` updated for the new routes;
  `e2e/smoke.spec.ts` now checks home → Start → map and that an old root link opens the map.

## 2026-11-12 · submission film v3: intro and outro around the screen recording

- Not part of the SPEC phases. `docs/campaign/video-v3/` is a Remotion 4 project that renders two films: the
  intro (≈88 s, before the screen recording) and the outro (≈77 s, after it). Together they leave ≈75 s of the
  240 s limit for the live demo. See `docs/campaign/video-v3/README.md` for how to join the three clips.
- Narration is the team's script, word for word, voiced in English by a Microsoft neural voice (edge-tts,
  `en-US-AndrewMultilingualNeural`, rate −5 %). There are no subtitles. Animations are keyed to word timestamps.
- All visuals are original vector illustration drawn in code (a family, a tin-roof house, the riverbank cross-section,
  satellites, a dotted globe from Natural Earth). The music and sound effects are synthesised by `scripts/score.py`
  (no stock audio). NASA appears as text only, with no logo.
- The Monpura outline is stylised and labelled "illustrative outline". The area figures (148 → 114 km²) come from
  the script. Screens of a future phone alert and an action checklist are labelled "illustration of a future version".
- `node_modules` is a junction to `../video-v2/node_modules` (the v2 sources were gone; only its install and renders
  remained).

## 2026-11-12 · submission film v3: 30 s team intro (00-team-intro)

- Added a third film before the story: the team's own intro speech, word for word, voiced with the same neural voice. The only text change is "Enum" → "Enam", to match the name supplied for the team slide.
- Palette: the film navy, with NASA Space Apps brand accents (Blue Yonder #2E96F5, Rocket Red #E43700) so it sits between Space Apps branding and the other two films.
- Running order is now 30 s + 88 s + recording + 77 s, which leaves about 45 s for the recording within 240 s (it was 75 s).

## 2026-11-12 · submission film v3: 16 s solution bridge (02-solution-before-demo)
- New clip between film 01 and the screen recording. Voice is the presenter's own recording (`vm/WhatsApp Audio 2026-11-12 at 19.34.10.mp4`), first 14.7 s only, ending on "...someone's home?". It is not TTS.
- Clip length is 16.5 s, against the requested ~14 s. That is 0.5 s lead-in + 14.4 s of speech + 1.6 s to hold the three answers and push back into the app.
- The first and last frames reproduce film 01's last frame (the app full screen). The clip can be cut in after 01 and before the recording with no transition needed.
- Word timings come from faster-whisper (small.en), run locally. The voice is high-passed, softly gated and gain-matched to the other films' voice (-16.5 dB RMS).
- Figures on the answer cards are taken from the app's own point card (Manpura): 80 m to bank, 19.4 m/yr retreat, score 67 High, river in 2–23 years.
- No-voice version is in out/no-voice/: same picture, bed only, at the same level.

## 2026-11-13 · final submission film (one continuous edit, 3:47.8)
- One Remotion composition (`Final`) replaces the hand-merged clips: thumbnail → team opener → story → solution bridge → screen recording + open data → impact → thumbnail. Output `out/final/TheLastSafeHome-NovaLogits-final.mp4`.
- Voice is now entirely the presenter's own recordings (z1/z2/z3 in final-version-contents/drive); the neural TTS voice is no longer used. Lines are cut by `scripts/final_vo.py` from faster-whisper word timings, dead air inside lines is shortened (pauses > 0.34 s become 0.26 s, 8.9 s removed in total), and the voice is sped up 4 % with pitch kept (ffmpeg atempo) so the film fits under 3:55.
- Every animated scene is re-timed to the presenter's words (timeline.json parts rebuilt by `scripts/final_timeline.py`; the TTS timeline is kept as `src/timeline-tts.json`).
- Screen recording: used at original speed and framing, never cropped or re-coloured, but cut into five segments (dissolves of 6 frames) so each action lands on its line. Unused: homepage, map loading, report scrolling, most of the compare drag and the long area-panel scroll.
- Music: one score for the whole film (`score.py final`), ducked 7 dB under every voice line, so there are no restarts at the joins.
- The official NASA Space Apps Challenge logo (supplied by the team, 440×172) now appears on the thumbnail, the team reveal, the team slide and the challenge scene. It is never drawn wider than its source. This replaces the earlier "NASA as text only" rule for this logo; no NASA insignia is used.
- Design changes requested by the team: the four-point "nova" star (read as the Gemini logo) is gone; "Arka Braja Prasad Nath" (not Prasadh) on screen; cards, pills and panels have 2–4 px corners; connectors are straight right-angled routes; no gradient text or glows; one type family (Fira Sans + Fira Sans Condensed, the Space Apps web typeface) replaces Manrope/Fraunces; labels in Blue Yonder, emphasis in amber, body in white/grey everywhere; the family figures have faces with expressions (worried during erosion, hopeful at the end).
- The intro's own "The Last Safe Home" title card was dropped: the solution section introduces the title a few seconds later, so the story now dives straight from the challenge page into the app.

## 2026-11-13 · 30-second summary teaser (submission rule)
- `Teaser` composition → `out/final/TheLastSafeHome-NovaLogits-30s.mp4`, 29.9 s. Voice is the presenter's own 30-second recording (final-version-contents/30sec), same cleaning as the final film, sped up 3 % so that a 0.9 s cold open and a 1.6 s end card fit under 30 s.
- Shot list: thumbnail cold open → team (logo, four members) → challenge page → erosion (house tips, worried family) → product title → NISAR radar → four cuts of the team's own screen recording (time slider, Monpura/Koyra switch landing on "Koyra", home risk card, 1988 compare, report) → mission at sunrise → thumbnail end card.
- Screen recording shown full frame with a slow 5 % push for motion in the teaser only; the full film keeps it unzoomed.

## 2026-11-13 · final film v2 (3:52.7): the team's own demo edit, uncut
- The demo section is now the team's edited screen recording (`final-version-contents/WhatsApp Video 2026-11-13 at 01.55.15.mp4` → `public/final/rec2.mp4`), played uncut from its first clean homepage frame (0.767 s; only the old bridge frame and the cut before it are trimmed) to its last frame. It shows the homepage, the 1988-vs-today slider moving and the area being drawn, which v1's cut-down segments missed.
- Voice over the clip sits exactly where the team placed it: the clip's soundtrack is the raw z1/z2 recording at constant offsets (clip − raw = −109.51 s for z1, +37.96 s for z2, +38.72 s for "We use free and open data"), measured with faster-whisper. Those lines are cut at natural speed with pauses kept (`scripts/demo_raw_vo.py` → `public/vo/r`); the clip's own audio is not used, so the voice has the same cleaning and level as the rest of the film.
- To stay under the team's new cap of 3:53, the rest of the film lost about 5 s of air: thumbnail 1.3 → 1.0 s, opener tail 2.3 → 1.8 s, intro lead and sentence gaps about 20 % shorter, bridge tail 1.3 → 1.0 s, outro gaps about 15 % shorter, end card 4.6 → 3.8 s. The last two demo lines ("We use free and open data…", "…previous research…") start on the clip's last second and run over the open-data scene, so they use the tightened take.
- The v1 timeline is kept as `src/timeline-v1.json`.

## 2026-11-13 · campaign folder tidied
- New layout under `docs/campaign/`: `submission/` (final deliverables), `source-materials/` (everything the team supplied, renamed from `final-version-contents/`, sorted into voice / scripts / screen-recordings / screenshots / brand), `video-v3/` (the Remotion project) and `video-v2/` (untouched). Index in `docs/campaign/README.md`.
- Earlier entries above still mention the old paths (`final-version-contents/drive`, `out/final`, `out/no-voice`, `vm/`); read them as: `source-materials/voice`, `submission/`, `video-v3/out/parts-no-voice`, `source-materials/voice/solution-intro-voice-full.mp4`.
- Scripts and README updated to the new paths (`final_vo.py`, `teaser_vo.py`, `bridge_vo.py`, `package.json`). Nothing was deleted except two regenerable caches (`video-v3/out/bundle`, `out/check`); the byte-identical copies of voice, thumbnail and story-film files were moved to `source-materials/archive/duplicates/`.
- `src/timeline-tts.json` and `src/timeline-v1.json` (unused snapshots) moved to `video-v3/archive/`.
