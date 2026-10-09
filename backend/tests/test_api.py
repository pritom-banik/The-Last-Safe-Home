from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analysis_is_labeled_as_simulated():
    response = client.post(
        "/api/analysis",
        json={
            "bbox": [90.19, 22.37, 90.41, 22.53],
            "start_date": "2025-01-01",
            "end_date": "2026-01-01",
            "change_type": "flood",
        },
    )

    assert response.status_code == 200
    assert response.json()["is_simulated"] is True
    assert response.json()["affected_area_km2"] == 31.2


def test_analysis_rejects_invalid_bbox():
    response = client.post(
        "/api/analysis",
        json={
            "bbox": [90.4, 22.5, 90.1, 22.3],
            "start_date": "2025-01-01",
            "end_date": "2026-01-01",
            "change_type": "flood",
        },
    )

    assert response.status_code == 422


def test_explanation_is_not_misrepresented_as_ai():
    response = client.post(
        "/api/ai/explain",
        json={
            "change_type": "flood",
            "affected_area_km2": 31.2,
            "change_percent": 68.4,
            "confidence": 0.91,
            "is_simulated": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["is_ai_generated"] is False