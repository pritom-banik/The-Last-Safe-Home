# The Last Safe Home

A web map that tracks **river-bank erosion and flooding in coastal Bangladesh** with radar from the
NASA–ISRO **NISAR** satellite and 38 years of Landsat images, and turns them into a **Home Risk Score (0–100)**
and an estimated range of **years until the river arrives** for any point you click. English and Bangla.

Built for NASA Space Apps Challenge 2026, challenge "Dancing with the SARs", by team **Nova Logits**
(Khulna local event): Pritom Banik, Arka Braja Prasad Nath, Megha Tania and Enam E Elahi. Open source (MIT).

> Every number is an estimate from satellite data, not an engineering survey. Use it to start a conversation
> with local authorities.

**What you can do:** click a point (score, years range, distance to the bank, retreat rate, flood frequency) ·
draw an area (land lost, buildings and people by risk class, NISAR scenes over it) · move through the 2026 NISAR
passes · swipe between 1988 and today · print a one-page report · read how it works on `/method`.

Sites: **Manpura Island, Bhola** and **Koyra, Khulna** (real data) and a synthetic **demo** site that works with no
downloads (shown with a red "DEMO DATA" banner).

---

## Screenshots: what each feature does and who uses it

All screenshots show **real data** for Manpura Island and Koyra (NISAR 2026 + Landsat 1988–2026), except where
marked as the demo site. They are made by `web/e2e/screenshots.manual.spec.ts` (see the file for how to refresh
them) and live in [`docs/screenshots/`](docs/screenshots/).

### 1. Site overview: Home Risk Score, water and bank lines

![Overview of Manpura with the Home Risk Score, water and bank lines](docs/screenshots/01-overview.png)

The map colours every piece of land by its **Home Risk Score** (green low → dark red severe), shows the water of
the selected NISAR pass in blue, and draws the river bank of every Landsat year since 1988 (purple → yellow) and
today's NISAR bank (white). The side panel sums up the site: land lost and gained since 1988, mean and fastest
bank retreat, buildings within 500 m of the bank, NISAR passes used.
**Real-life use:** a union parishad member or an NGO field officer sees at a glance which shores are eating into
villages and where the land is growing, before planning a visit or a meeting.

### 2. Point card: "When could the river reach this house?"

![Point card for a high-risk point on Manpura](docs/screenshots/02-point-card.png)

Click any point: its score (0–100) and class with plain advice, the estimated **range of years until the river
arrives**, the distance to today's bank, the bank's retreat rate (± its uncertainty), how often the spot flooded in
2026, and "How is this calculated?" with the formula and its parts. Every card carries the disclaimer.
**Real-life use:** a family deciding whether to rebuild on the same plot, or a local official checking a school or
cyclone shelter site, gets a number and a time range they can bring to the union parishad — "Copy link" shares
exactly this view.

### 3. Draw an area: statistics and NISAR scenes

![Statistics for a drawn area with the list of NISAR scenes](docs/screenshots/03-area-statistics.png)

Draw any shape: area and land area, land lost per year, mean score, buildings (total, within 100 m and 500 m of the
bank), **people by risk class** (WorldPop estimate), transects inside, and a live list of the NISAR scenes over the
area with "Open in ASF" links. The shape can be downloaded as GeoJSON.
**Real-life use:** a relief or resettlement planner outlines a ward or a char and gets how many homes and people
sit near a retreating bank; a researcher finds which NISAR radar scenes cover their study area.

### 4. Radar image and time slider

![NISAR radar image on 17 August 2026 with the water mask and bank lines](docs/screenshots/04-radar-time-slider.png)

The NISAR radar image (HH backscatter: water dark, land bright) for any 2026 pass, with that day's water. The
slider steps through the passes (play, arrow keys); the July–August instrument gap is marked.
**Real-life use:** watch the monsoon flood spread and drain pass by pass, through clouds that block ordinary
satellite photos — useful for disaster-management staff after heavy rain or a cyclone.

### 5. Flood frequency

![Flood frequency over Manpura in the 2026 monsoon](docs/screenshots/05-flood-frequency.png)

How often each place was under water across the 2026 NISAR passes (light = rarely, dark blue = almost always).
**Real-life use:** shows which fields, roads and homesteads flood repeatedly in the monsoon — where raised plinths,
embankment repair or drainage would help most.

### 6. Transects: how fast each stretch of bank moves

![Transects around Manpura coloured by bank retreat rate](docs/screenshots/06-transects.png)

Lines every 100 m across the bank, coloured by the bank's speed since 1988 (red = retreating, blue = growing,
± 60 m/yr). The retreat rates drive the "years until the river arrives".
**Real-life use:** engineers and the Water Development Board can see which stretches erode fastest and compare them
with where protection works exist.

### 7. Compare 1988 with today

![Swipe comparison of the 1988 Landsat bank and the 2026 NISAR bank](docs/screenshots/07-compare-1988-2026.png)

Drag the handle (or use the arrow keys) to swipe between the 1988 dry-season shoreline (Landsat) and the latest
NISAR shoreline.
**Real-life use:** the clearest way to show a community meeting, a journalist or a donor how much land has gone in
one generation.

### 8. Union statistics

![Statistics for Manpura union](docs/screenshots/08-union-statistics.png)

Click a union name: land area, mean score, land lost per year, buildings and people by risk class.
**Real-life use:** union and upazila officials compare their unions to set priorities for a budget or an
adaptation plan.

### 9. Bangla

![The point card in Bangla](docs/screenshots/09-bangla.png)

Every label, number and date switches to Bangla (বাংলা) with one button; the language stays in the link.
**Real-life use:** people on the char and local officials read the results in their own language.

### 10. Printable report

![One-page printable report for a point](docs/screenshots/10-report.png)

"Print report" opens an A4 page — map, the numbers, a three-line method summary, the disclaimer, data credits and a
link back to the view — to print or save as PDF (Bangla prints correctly).
**Real-life use:** take a paper copy to the union parishad, attach it to a relocation request, or hand it out at a
community meeting where there is no internet.

### 11. Method and live validation

![Method page with validation numbers for Manpura](docs/screenshots/11-method-validation.png)

How everything is calculated, in plain words (English and Bangla), with the site's live validation numbers
(land area vs a published study, water map vs a Sentinel-2 image), the limitations and the data credits.
**Real-life use:** lets a reviewer, journalist or official judge how far to trust the numbers before acting on them.

### 12. About

![About page with the team](docs/screenshots/12-about.png)

What the project is, the team, the licence and repository link, and the data credits.

### 13. Second site: Koyra, Khulna

![Home Risk Score for Koyra](docs/screenshots/13-koyra.png)

The same analysis for Koyra on the edge of the Sundarbans (NISAR track 170). New sites are added with one config
file (see "Adding a new site").

### 14. Demo site (no downloads)

![The synthetic demo site with its red banner](docs/screenshots/14-demo-site.png)

A synthetic river that makes the whole app work without any downloads or logins — for trying the app, teaching and
tests. A red "DEMO DATA — not real measurements" banner is always shown.

### 15–16. Phones

<p>
  <img src="docs/screenshots/15-phone-layers.png" alt="Phone layout with the layers sheet" width="280" />
  &nbsp;
  <img src="docs/screenshots/16-phone-point-card.png" alt="Point card on a phone" width="280" />
</p>

On phones the side panel becomes a bottom sheet (Layers · Site summary) and the point card fills the screen.
**Real-life use:** most people in coastal Bangladesh are online by mobile phone — the app works on a phone in the
field, standing on the bank itself.

---

## Quick start (demo site, no credentials)

With conda and make (Linux/macOS/WSL):

```bash
make setup     # conda env `lsh` from environment.yml + npm install in web/
make demo      # synthetic demo site -> data/processed/demo
make api       # API on http://localhost:8000/api/v1/health
make web       # app on http://localhost:5173/ (home page) · map: http://localhost:5173/map?site=demo
```

With Docker only:

```bash
make demo      # or: python -m pipeline.cli all --site demo   (needs the Python env once)
make up        # docker compose: API + web (nginx) -> http://localhost:8080/map?site=demo
make down
```

Without conda/make (e.g. Windows, Python 3.11–3.12, Node 20+):

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt          # .venv/bin/python on Linux/macOS
.venv/Scripts/python -m pipeline.cli all --site demo
.venv/Scripts/python -m uvicorn api.app.main:app --reload       # http://localhost:8000
cd web && npm install && npm run dev                            # http://localhost:5173/map?site=demo
```

Tests: `make test` (pytest + vitest), `make lint` (ruff + eslint), `make e2e` (Playwright starts the API and the
built app itself; first run `cd web && npx playwright install chromium`).

Pages: `/` home page · `/map` the map · `/method` how it works + live validation · `/about` ·
`/report?site=&lon=&lat=` (or `&polygon=`) printable report — use the browser's "Save as PDF".

## Real data for a site

1. Copy `.env.example` to `.env` and fill in your **NASA Earthdata** login. Never commit `.env` or `data/`.
   ASF only serves NISAR once (a) the **Study Area** field of your Earthdata profile
   (https://urs.earthdata.nasa.gov/profile) is filled in and (b) the ASF data application is authorized; the
   pipeline stops with the link if not.
2. Search NISAR and look at the inventory (no download):
   `make inventory SITE=manpura` → `data/raw/manpura/nisar/inventory.csv`. If more than one track has
   ≥ 6 usable passes, the step stops: set `nisar.track` in `config/sites/<site>.yaml`.
3. Download: `make fetch SITE=manpura` — NISAR **AOI subsets** read over HTTP range requests (~0.6–1 GB kept,
   ~35 min; `--full` downloads whole 6 GB files and refuses more than 20 GB unless confirmed), Landsat
   composites from Planetary Computer, OSM buildings, WorldPop and union boundaries.
4. Process: `make pipeline SITE=manpura` (gcov → water-sar → landsat → banklines → transects → flood → motion →
   context → score → validate → publish), or one step with `STEP=`. Steps skip outputs that exist (`--force`
   redoes them). Each writes a summary to `data/processed/<site>/summaries/<step>.json`.
5. Optional accuracy check: `python -m pipeline.cli validate --site manpura --make-points`, label the 200 points
   in `data/raw/manpura/validation/points.csv` (`water`/`land`) from Sentinel-2, run `validate` again.

## Adding a new site

1. Create `config/sites/<id>.yaml` by copying `manpura.yaml` and change: `id`, `name.en` / `name.bn`, `aoi_wkt`
   (a lon/lat polygon, keep it under ~0.35° × 0.35°), `utm_epsg` (UTM zone of the AOI: 32645 west of 90°E, 32646
   east of it in Bangladesh), `center`, `zoom`, and `nisar.track: null`. Remove `validation.published_area_km2`
   unless you have published land areas for the site (then also list `validation.island_unions`).
2. Check it parses: `python -m pipeline.cli show-config --site <id>`.
3. Run steps 2–4 of "Real data" above with `SITE=<id>`; choose the track with the most HH passes covering the
   whole AOI (`aoi_cover` = 1 in the inventory).
4. Add the id to `SITES` in `.env` (and in the API's environment when deployed). The site appears in the site
   selector once its `layers.json` exists.
5. Look at the sanity checks in `docs/DECISIONS.md` (phase 6): rates within ±200 m/yr, ≥ 80 % of transects with a
   rate, score not all one class, water mask vs Sentinel-2 (`validation.json`).

## Deploying

The API serves files from `data/processed/`, which is not in git. `make pack` (or
`python -m pipeline.lsh.pack --sites manpura,koyra,demo --tar data/deploy/lsh-data.tar.gz`) writes a deploy
copy with only the served files — radar dB layers rounded to 0.1 dB, the unused HV layer left out — and **fails
over 1.5 GB**. Manpura packs to ~300 MB.

**API (Render, Docker web service, `render.yaml`)**

1. Upload `data/deploy/lsh-data.tar.gz` somewhere public, e.g. as an asset of a GitHub release (`data-v1`).
2. In Render: *New → Blueprint* on this repository. Set `DATA_URL` (the archive's URL) and `CORS_ORIGINS`
   (the web app's origin). The image downloads the data at build time; health check `/api/v1/health`.
   Memory: ~260 MB with Manpura + demo loaded (measured); the free tier has 512 MB, so load fewer `SITES` if a
   third site does not fit.
3. Or build locally with the data baked in: `make build-api` (Docker with BuildKit), push the image to a
   registry and deploy that image (Render, Railway, Fly.io…).

**Web (Vercel, `vercel.json`)**: import the repository (root directory = repo root), set the environment
variable `VITE_API_URL=https://<api-host>/api/v1`, deploy. **GitHub Pages** instead: set the repository
variable `API_URL=https://<api-host>` and run the `pages` workflow by hand (it builds under `/<repo>/` and adds the
SPA fallback). Free API tiers sleep: the app pings `/health` first and says "Waking up the server…".

**Static edition (no API at all)**: `make static` writes `data/static/` (API-shaped JSON, pre-rendered PNG tiles
for zoom 8–14, and every site's point answers on a ~100 m grid, made by the API's own code) and builds
`web/dist-static/` with it inside — ~30 MB for Manpura + demo. Host that folder anywhere static (with the SPA
fallback). Clicks are answered for the ~100 m grid cell (the card says so); the radar backscatter layer, area
statistics and the NISAR scene search need the live API and say so. Useful as a fallback when the API host is
down or asleep.

## Repository layout

`config/sites/` site files · `pipeline/` offline Python processing (`python -m pipeline.cli <step> --site <id>`)
· `api/` FastAPI backend (+ `Dockerfile`) · `web/` React + MapLibre app (+ `Dockerfile`, nginx config) ·
`docs/METHOD.md` (+ `METHOD.bn.md`) the method in plain words, shown on `/method` · `docs/DECISIONS.md` every
deviation from [SPEC.md](SPEC.md) · `docker-compose.yml`, `render.yaml`, `vercel.json` deployment.

## Data credits

- NISAR data courtesy of NASA/JPL-Caltech and ISRO, via ASF DAAC (provisional `PR` products, 2026).
- Landsat data courtesy of the U.S. Geological Survey (Collection 2 Level 2), accessed through Microsoft
  Planetary Computer.
- Sentinel-2 (validation only): contains modified Copernicus Sentinel data 2026, via Microsoft Planetary Computer.
- Buildings, roads and facilities © OpenStreetMap contributors (ODbL), via the Overpass API. Basemap © OpenStreetMap
  contributors; satellite basemap © Esri, Maxar, Earthstar Geographics.
- Population: WorldPop (www.worldpop.org), Bangladesh 100 m constrained estimates 2025 (R2025A), CC BY 4.0.
- Union boundaries: geoBoundaries (Runfola et al. 2020), source Bangladesh Bureau of Statistics / OCHA ROAP,
  CC BY 3.0 IGO.

This project is not endorsed by NASA or ISRO and does not use their logos.

## Limitations

- NISAR products are **provisional** (first data 17 June 2026; validated products planned for the end of 2026);
  no data 27 July – 10 August 2026 (instrument gap).
- Monsoon radar maps flooded fields and wet mud as water. Bank lines use only NISAR water near the dry-season
  river, but today's bank still sits ~50–80 m inland of a Sentinel-2 outline at Manpura (different tide, wet
  mud), so "years until the river" errs on the early side.
- "Years until the river arrives" extrapolates the 1988–2026 average retreat rate; rivers change course. The range
  is only the statistical spread of that rate.
- Ground movement (InSAR) is unusable over wet, vegetated deltas (Manpura: 0.2 % coherent land) and is then left
  out of the score.
- People and building counts come from WorldPop and OpenStreetMap, which miss homes.
- The water maps are not yet checked against hand-labelled points (`validation.json` says so; see step 5 above).
- Bangla text still needs a native speaker's review.

Details and numbers: `/method` in the app and `docs/DECISIONS.md`.

## Licence

[MIT](LICENSE)
