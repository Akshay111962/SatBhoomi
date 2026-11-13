"""Integration tests for SatBhoomi API Contract v1 and Mock Mode."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from satbhoomi.api.main import app, lifespan
from satbhoomi.api.mock_data import FAKE_MOCK_TOKEN
from satbhoomi.api.schemas.alerts import AlertActionResponse
from satbhoomi.api.schemas.assessments import AssessmentResponse
from satbhoomi.api.schemas.auth import TokenResponse
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.api.schemas.farmer_summary import FarmerSummaryResponse
from satbhoomi.api.schemas.monitoring import PlotMonitoringResponse
from satbhoomi.api.schemas.plots import PlotListResponse, PlotResponse
from satbhoomi.api.schemas.relief import ReliefReportResponse
from satbhoomi.api.schemas.what_if import WhatIfResponse
from satbhoomi.config.settings import get_settings


@pytest.fixture
def mock_client():
    """TestClient configured with MOCK_API=true."""
    get_settings.cache_clear()
    with patch.dict(os.environ, {"MOCK_API": "true", "APP_ENV": "development"}):
        with TestClient(app) as client:
            yield client
    get_settings.cache_clear()


@pytest.fixture
def non_mock_client():
    """TestClient configured with MOCK_API=false (default)."""
    get_settings.cache_clear()
    with patch.dict(os.environ, {"MOCK_API": "false", "APP_ENV": "development"}):
        with TestClient(app) as client:
            yield client
    get_settings.cache_clear()


AUTH_HEADERS = {"Authorization": f"Bearer {FAKE_MOCK_TOKEN}"}


def test_mock_mode_every_endpoint_returns_200_or_201_and_validates(mock_client: TestClient) -> None:
    """In mock mode, every business endpoint returns 200/201 and validates against its schema."""
    # 1. POST /api/v1/auth/login
    resp = mock_client.post(
        "/api/v1/auth/login", json={"username": "officer_test", "password": "valid_password"}
    )
    assert resp.status_code == 200
    token_obj = TokenResponse.model_validate(resp.json())
    assert token_obj.access_token == FAKE_MOCK_TOKEN
    assert token_obj.meta is not None
    assert token_obj.meta.synthetic is True

    # 2. POST /api/v1/plots
    plot_payload = {
        "farmer_id": 1,
        "crop": "wheat",
        "area_acre": 2.5,
        "district": "Anand",
        "village": "Boriavi",
        "irrigation": "tube_well",
        "insured": 1,
    }
    resp = mock_client.post("/api/v1/plots", json=plot_payload, headers=AUTH_HEADERS)
    assert resp.status_code == 201
    plot_obj = PlotResponse.model_validate(resp.json())
    assert plot_obj.plot_code.startswith("PLOT-")
    assert plot_obj.meta is not None
    assert plot_obj.meta.synthetic is True

    # 3. GET /api/v1/plots
    resp = mock_client.get("/api/v1/plots?limit=5&offset=0", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    plots_list = PlotListResponse.model_validate(resp.json())
    assert len(plots_list.items) > 0
    assert plots_list.total >= 5

    # 4. POST /api/v1/plots/1/assessments
    resp = mock_client.post(
        "/api/v1/plots/1/assessments",
        json={"season": "2024-25"},
        headers={"Idempotency-Key": "test-key-123", **AUTH_HEADERS},
    )
    assert resp.status_code == 201
    asm_create = AssessmentResponse.model_validate(resp.json())
    assert asm_create.plot_id == 1
    assert len(asm_create.reasons) == 3

    # 5. GET /api/v1/assessments/1
    resp = mock_client.get("/api/v1/assessments/1", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    asm_get = AssessmentResponse.model_validate(resp.json())
    assert asm_get.score == 18
    assert asm_get.band == "low"
    assert len(asm_get.reasons) == 3

    # 6. POST /api/v1/assessments/1/what-if
    resp = mock_client.post(
        "/api/v1/assessments/1/what-if",
        json={"changed_input": "insured", "new_value": "1"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    what_if = WhatIfResponse.model_validate(resp.json())
    assert what_if.estimate_label == "estimate"
    assert "causation" in what_if.causation_disclaimer.lower()

    # 7. GET /api/v1/plots/1/monitoring
    resp = mock_client.get("/api/v1/plots/1/monitoring", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    monitoring = PlotMonitoringResponse.model_validate(resp.json())
    assert len(monitoring.timeline) > 0

    # 8. POST /api/v1/alerts/101/actions
    resp = mock_client.post(
        "/api/v1/alerts/101/actions",
        json={
            "action_type": "supportive_field_visit",
            "note": "Supportive visit conducted; water available.",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    action = AlertActionResponse.model_validate(resp.json())
    assert action.alert_id == 101

    # 9. GET /api/v1/plots/3/relief-report
    resp = mock_client.get("/api/v1/plots/3/relief-report", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    relief = ReliefReportResponse.model_validate(resp.json())
    assert relief.exceeds_rbi_33_threshold is True
    assert "official crop loss assessment" in relief.disclaimer.lower()

    # 10. GET /api/v1/assessments/1/farmer-summary for en, gu, hi
    for lang in ["en", "gu", "hi"]:
        resp = mock_client.get(
            f"/api/v1/assessments/1/farmer-summary?lang={lang}", headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        summary = FarmerSummaryResponse.model_validate(resp.json())
        assert summary.lang == lang
        assert summary.source in ("template", "reviewed")
        assert len(summary.key_points) > 0


def test_mock_error_examples_match_standard_error_body(mock_client: TestClient) -> None:
    """Mock error examples conform strictly to {"error": {"code", "message", "field"}}."""
    # 400 Bad Request
    resp = mock_client.post(
        "/api/v1/plots",
        json={"farmer_id": 1, "area_acre": -5.0},  # invalid area
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    err_400 = ErrorResponse.model_validate(resp.json())
    assert err_400.error.code == "VALIDATION_ERROR"
    assert err_400.error.field == "area_acre"

    # 401 Unauthorized (invalid password)
    resp = mock_client.post(
        "/api/v1/auth/login", json={"username": "user", "password": "wrong_password"}
    )
    assert resp.status_code == 401
    err_401 = ErrorResponse.model_validate(resp.json())
    assert err_401.error.code == "INVALID_CREDENTIALS"

    # 401 Unauthorized (missing header on protected route)
    resp = mock_client.get("/api/v1/plots")
    assert resp.status_code == 401
    err_no_auth = ErrorResponse.model_validate(resp.json())
    assert err_no_auth.error.code == "UNAUTHORIZED"

    # 403 Forbidden (simulated via header)
    resp = mock_client.get("/api/v1/plots", headers={"X-Mock-Error": "403", **AUTH_HEADERS})
    assert resp.status_code == 403
    err_403 = ErrorResponse.model_validate(resp.json())
    assert err_403.error.code == "FORBIDDEN"

    # 404 Not Found (non-existent plot)
    resp = mock_client.get("/api/v1/assessments/999", headers=AUTH_HEADERS)
    assert resp.status_code == 404
    err_404 = ErrorResponse.model_validate(resp.json())
    assert err_404.error.code == "NOT_FOUND"

    # 429 Rate Limit Exceeded (simulated via header)
    resp = mock_client.get("/api/v1/plots", headers={"X-Mock-Error": "429", **AUTH_HEADERS})
    assert resp.status_code == 429
    err_429 = ErrorResponse.model_validate(resp.json())
    assert err_429.error.code == "RATE_LIMIT_EXCEEDED"


def test_without_mock_api_every_business_endpoint_returns_501(non_mock_client: TestClient) -> None:
    """When MOCK_API=false, every business endpoint returns 501; /health remains operational."""
    # Health check works normally
    resp = non_mock_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["mock_api"] is False

    # Business endpoints return 501 Not Implemented with standard error body
    endpoints = [
        ("POST", "/api/v1/auth/login", {"username": "officer_test", "password": "password_123"}),
        ("POST", "/api/v1/plots", {"farmer_id": 1, "area_acre": 2.0}),
        ("GET", "/api/v1/plots", None),
        ("POST", "/api/v1/plots/1/assessments", {"season": "2024-25"}),
        ("GET", "/api/v1/assessments/1", None),
        ("POST", "/api/v1/assessments/1/what-if", {"changed_input": "insured", "new_value": "1"}),
        ("GET", "/api/v1/plots/1/monitoring", None),
        (
            "POST",
            "/api/v1/alerts/1/actions",
            {"action_type": "supportive_field_visit", "note": "Supportive visit logged"},
        ),
        ("GET", "/api/v1/plots/1/relief-report", None),
        ("GET", "/api/v1/assessments/1/farmer-summary?lang=en", None),
    ]

    for method, path, body in endpoints:
        if method == "POST":
            resp = non_mock_client.post(path, json=body or {})
        else:
            resp = non_mock_client.get(path)

        assert resp.status_code == 501, f"Expected 501 for {method} {path}, got {resp.status_code}"
        err = ErrorResponse.model_validate(resp.json())
        assert err.error.code == "NOT_IMPLEMENTED"


@pytest.mark.anyio
async def test_app_refuses_to_start_in_mock_mode_when_production() -> None:
    """FastAPI application must refuse to start in mock mode if ENVIRONMENT=production."""
    get_settings.cache_clear()
    with patch.dict(os.environ, {"MOCK_API": "true", "ENVIRONMENT": "production"}):
        with pytest.raises(RuntimeError, match="MOCK_API cannot be enabled in production"):
            async with lifespan(app):
                pass
    get_settings.cache_clear()


def test_cors_origins_enforcement(mock_client: TestClient) -> None:
    """CORS middleware allows configured origins and rejects unlisted origins."""
    # Allowed origin: http://localhost:5173
    resp = mock_client.options(
        "/api/v1/plots",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Disallowed origin: http://malicious-domain.com
    resp = mock_client.options(
        "/api/v1/plots",
        headers={
            "Origin": "http://malicious-domain.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") is None
