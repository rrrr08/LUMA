"""
Legacy router smoke tests — kept for regression coverage.
Refactored to use shared conftest.py DB fixture.
Full coverage is in tests/integration/test_project_router.py
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_project_returns_valid_response():
    response = client.post(
        f"{settings.API_V1_STR}/projects",
        json={"name": "Legacy Smoke Test Project"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Legacy Smoke Test Project"
    assert "id" in data


def test_get_projects_list_is_list():
    client.post(f"{settings.API_V1_STR}/projects", json={"name": "Smoke List Project"})
    response = client.get(f"{settings.API_V1_STR}/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1
