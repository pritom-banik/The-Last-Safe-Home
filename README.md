# The Last Safe Home

An Earth-observation change intelligence prototype inspired by the project proposal. The first demo centers on selecting an area, comparing dates, discovering NASA observations through CMR, and presenting a clearly labeled illustrative flood analysis.



## Run the demo

Requirements: Node.js 20+ and Python 3.11+ (tested with Python 3.12). On Windows, select Python 3.12 explicitly if multiple runtimes are installed.

1. Start the API in a terminal:

   ```powershell
   cd backend
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

2. Start the frontend in another terminal:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

3. Open the Vite URL (usually `http://localhost:5173`). The map uses OpenFreeMap vector tiles and needs an internet connection. The API runs at `http://localhost:8000`; interactive API docs are at `http://localhost:8000/docs`.

Use **Find NASA observations** to query CMR for metadata matching the current map area and dates. **Run illustrative analysis** returns an example response from the local API. Without the API, the interface falls back to the same clearly marked local example.

## Project layout

```text
frontend/       React + TypeScript + MapLibre dashboard
backend/        FastAPI endpoints, CMR client, and demo analysis
data/sample/    Sample-data provenance and input conventions
data/processed/ Reserved for generated GeoJSON and rasters
ml/             Reserved for model training and inference
docs/           Architecture, methodology, and NASA data notes
```

## API

- `GET /health`
- `POST /api/analysis` accepts a bounding box, date range, and change type; returns a simulated result with `is_simulated: true`.
- `GET /api/nasa/search` queries NASA CMR granule metadata for a bounding box, date range, and optional keyword.
- `POST /api/ai/explain` produces a deterministic explanation from supplied metrics. It is not an LLM and does not infer measurements.

NASA Earthdata credentials are intentionally not needed for public CMR metadata search. Any credentials needed for protected data belong on the backend, never in frontend environment variables.

## Next milestones

1. Agree on a validated water-detection dataset and acquisition window.
2. Retrieve and preprocess compatible observations; document calibration, co-registration, and masking.
3. Replace the illustrative analysis with tested raster change detection and traceable provenance.
4. Persist jobs and results in PostGIS; add asynchronous processing when job duration warrants it.
5. Add AI explanations only after they consume validated outputs, with evidence and uncertainty included.