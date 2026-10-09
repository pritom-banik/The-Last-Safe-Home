from datetime import date

import httpx

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"


async def search_granules(
    bbox: list[float],
    start_date: date,
    end_date: date,
    keyword: str,
) -> list[dict[str, str | None]]:
    params = {
        "bounding_box": ",".join(str(value) for value in bbox),
        "temporal": f"{start_date.isoformat()}T00:00:00Z,{end_date.isoformat()}T23:59:59Z",
        "keyword": keyword,
        "page_size": 10,
        "sort_key": "-start_date",
    }
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(CMR_GRANULES_URL, params=params)
        response.raise_for_status()
    entries = response.json().get("feed", {}).get("entry", [])
    return [
        {
            "title": entry.get("title", "Untitled NASA observation"),
            "start_date": entry.get("time_start"),
            "end_date": entry.get("time_end"),
            "collection_id": entry.get("collection_concept_id"),
            "producer_id": entry.get("producer_id"),
        }
        for entry in entries
    ]