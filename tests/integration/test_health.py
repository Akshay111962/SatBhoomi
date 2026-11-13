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


def test_unregistered_route_returns_404(test_client: TestClient) -> None:
    """Verify that unregistered routes return 404 Not Found."""
    response = test_client.get("/api/v1/unknown-route")
    assert response.status_code == 404


def test_business_endpoints_return_501_in_default_mode(test_client: TestClient) -> None:
    """Verify that registered business routes return 501 in default non-mock mode."""
    response = test_client.get("/api/v1/plots")
    assert response.status_code == 501
