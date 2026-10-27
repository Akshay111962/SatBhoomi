"""Pytest fixtures for SatBhoomi test suite."""

import pytest
from fastapi.testclient import TestClient

from satbhoomi.api.main import app
from satbhoomi.config.settings import Settings, get_settings


@pytest.fixture
def test_client() -> TestClient:
    """Fixture providing a FastAPI test client instance."""
    return TestClient(app)


@pytest.fixture
def clean_settings() -> Settings:
    """Fixture providing freshly instantiated default settings."""
    get_settings.cache_clear()
    return get_settings()
