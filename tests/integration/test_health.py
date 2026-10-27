"""Integration tests for FastAPI health check route."""

from fastapi.testclient import TestClient


def test_health_check_endpoint(test_client: TestClient) -> None:
    """Verify that GET /health returns 200 OK with expected system metadata."""
    response = test_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "SatBhoomi Score + Raksha"
    assert "version" in data
    assert "environment" in data


def test_only_health_endpoint_registered(test_client: TestClient) -> None:
    """Verify that unexposed business routes return 404 in this foundation phase."""
    response = test_client.get("/api/v1/plots")
    assert response.status_code == 404
