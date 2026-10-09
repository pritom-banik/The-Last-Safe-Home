# NASA data discovery

The backend searches NASA's Common Metadata Repository (CMR) granule endpoint at `https://cmr.earthdata.nasa.gov/search/granules.json`. It accepts a geographic bounding box, date interval, and keyword and returns a small metadata summary. This is discovery only; it does not retrieve granule assets or imply that a compatible image pair exists.

The prototype uses public CMR search and does not require an Earthdata token. If a future data product needs authenticated downloads, keep tokens server-side in environment variables or a secret manager. Never commit credentials or expose them through `VITE_` frontend variables.