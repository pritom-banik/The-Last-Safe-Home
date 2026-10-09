# Architecture

## Current prototype

```text
React + TypeScript + MapLibre
        │ analysis / metadata requests
        ▼
FastAPI ───────────────► NASA CMR granule metadata
   │
   └── illustrative analysis response (explicitly simulated)
```

The browser never receives Earthdata credentials. The CMR integration searches public granule metadata only; it does not download or process science data. The analysis endpoint deliberately returns a fixture so the interaction can be demonstrated before a validated processing pipeline exists.

## Planned evolution

Add a scientific processing worker for selected products, persist AOIs and jobs with PostgreSQL/PostGIS, and store generated rasters in object storage. Add Redis/Celery only when actual processing jobs require a queue. AI explanations should consume validated measurements and carry uncertainty/provenance, never invent them.