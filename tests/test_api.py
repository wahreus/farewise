"""Tests for FareWise API health and analysis endpoints."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.models import (AnalysisResponse,
                            InputSummaryResponse,
                            PaygSelectionResponse)


class FakeAnalysisService:
    """Minimal analysis service used to isolate API endpoint behavior."""
    def __init__(self, ready: bool = True) -> None:
        """Initialize the fake service with a readiness state."""
        self.ready = ready

    def is_ready(self) -> bool:
        """Return whether the fake analysis service is ready."""
        return self.ready

    def analyze_file(self, csv_path: Path) -> AnalysisResponse:
        """Validate the uploaded file and return a fixed analysis response."""
        assert csv_path.read_text(encoding="utf-8") == "journey data"
        return AnalysisResponse(
            journey_start_date=date(2026, 1, 1),
            journey_end_date=date(2026, 1, 1),
            recorded_payg_total="8.50",
            optimized_total="8.50",
            estimated_saving="0.00",
            uses_travelcard=False,
            input_summary=InputSummaryResponse(
                loaded_journeys=2,
                skipped_rows=0,
                unsupported_transport_modes=0,
                non_journey_actions=0,
                unknown_stations=0,
                invalid_charges=0),
            selections=[PaygSelectionResponse(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 1),
                total_cost="8.50",
                journey_count=2)],
            warnings=[])


def test_liveness_returns_alive() -> None:
    """Verify that liveness returns alive."""
    client = TestClient(create_app(FakeAnalysisService()))
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_returns_503_when_dependencies_are_missing() -> None:
    """Verify that readiness returns 503 when dependencies are missing."""
    client = TestClient(create_app(FakeAnalysisService(ready=False)))
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "FareWise reference data is unavailable"}


def test_create_analysis_returns_structured_result() -> None:
    """Verify that create analysis returns structured result."""
    client = TestClient(create_app(FakeAnalysisService()))
    response = client.post(
        "/analyses",
        files={"file": ("journeys.csv", b"journey data", "text/csv")})
    assert response.status_code == 200
    assert response.json()["recorded_payg_total"] == "8.50"
    assert response.json()["input_summary"]["loaded_journeys"] == 2
    assert response.json()["selections"][0]["payment_type"] == "payg"


def test_create_analysis_rejects_non_csv_file() -> None:
    """Verify that create analysis rejects non CSV file."""
    client = TestClient(create_app(FakeAnalysisService()))
    response = client.post(
        "/analyses",
        files={"file": ("journeys.txt", b"journey data", "text/plain")})
    assert response.status_code == 415
