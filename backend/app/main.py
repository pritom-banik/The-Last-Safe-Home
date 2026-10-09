from datetime import date
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from app.nasa.cmr import search_granules

ChangeType = Literal["flood", "wildfire", "deforestation", "agriculture"]

app = FastAPI(title="The Last Safe Home API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    bbox: list[float] = Field(min_length=4, max_length=4)
    start_date: date
    end_date: date
    change_type: ChangeType = "flood"

    @model_validator(mode="after")
    def validate_analysis_window(self):
        west, south, east, north = self.bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("bbox must be [west, south, east, north] in valid geographic bounds")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        return self


class ExplanationRequest(BaseModel):
    change_type: ChangeType
    affected_area_km2: float = Field(ge=0)
    change_percent: float
    confidence: float = Field(ge=0, le=1)
    is_simulated: bool = True


@app.get("/health")
async def health():
    return {"status": "ok", "service": "the-last-safe-home-api"}


@app.post("/api/analysis")
async def create_analysis(request: AnalysisRequest):
    examples = {
        "flood": (31.2, 68.4, 0.91, "High"),
        "wildfire": (18.6, 22.1, 0.84, "Moderate"),
        "deforestation": (12.4, -4.8, 0.79, "Moderate"),
        "agriculture": (9.7, 13.2, 0.76, "Low"),
    }
    area, change, confidence, severity = examples[request.change_type]
    return {
        "status": "illustrative",
        "change_type": request.change_type,
        "affected_area_km2": area,
        "change_percent": change,
        "confidence": confidence,
        "severity": severity,
        "risk_level": severity,
        "explanation": (
            f"Illustrative {request.change_type} scenario: {abs(change):.1f}% change across "
            f"{area:.1f} km². This example is not derived from satellite imagery."
        ),
        "is_simulated": True,
        "source_label": "Illustrative demo scenario; no imagery processed",
    }


@app.get("/api/nasa/search")
async def nasa_search(
    start_date: date,
    end_date: date,
    bbox: str = Query(description="west,south,east,north"),
    keyword: str = Query(default="water", max_length=80),
):
    try:
        bounds = [float(value) for value in bbox.split(",")]
    except ValueError as error:
        raise HTTPException(status_code=422, detail="bbox must contain four comma-separated numbers") from error
    try:
        request = AnalysisRequest(
            bbox=bounds,
            start_date=start_date,
            end_date=end_date,
            change_type="flood",
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if request.start_date >= request.end_date:
        raise HTTPException(status_code=422, detail="start_date must be earlier than end_date")
    try:
        observations = await search_granules(
            request.bbox,
            request.start_date,
            request.end_date,
            keyword,
        )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="NASA CMR metadata search failed") from error
    return {"source": "NASA CMR", "observations": observations}


@app.post("/api/ai/explain")
async def explain_analysis(request: ExplanationRequest):
    direction = "increase" if request.change_percent >= 0 else "decrease"
    qualifier = "illustrative " if request.is_simulated else "observed "
    return {
        "explanation": (
            f"This {qualifier}{request.change_type} result indicates a {abs(request.change_percent):.1f}% "
            f"{direction} over {request.affected_area_km2:.1f} km². The supplied confidence is "
            f"{request.confidence:.0%}."
        ),
        "is_ai_generated": False,
        "is_simulated": request.is_simulated,
    }