import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.repositories.project_repo import ProjectRepository, ApiEndpointRepository, SourceRepository, SchemaRepository, ExtractorRepository
from tests.conftest import TestingSessionLocal
from app.routers import runtime_router

client = TestClient(app)

# Helper function to set up a project owned by the test user (test@x.com)
def _setup_project_for_test() -> str:
    db = TestingSessionLocal()
    try:
        from app.repositories.project_repo import UserRepository
        user = UserRepository(db).get_by_email("test@x.com")
        if not user:
            user = UserRepository(db).create("test@x.com", "testpass123", "user")
        
        project = ProjectRepository(db).create(user.id, "Integration Test Project")
        db.commit()
        return project.id
    finally:
        db.close()

def test_webhook_crud_operations():
    project_id = _setup_project_for_test()
    
    # 1. Create Webhook Config
    payload = {
        "url": "https://callback.com/webhooks",
        "trigger_type": "on_change",
        "is_active": True
    }
    response = client.post(
        f"{settings.API_V1_STR}/projects/{project_id}/webhooks",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://callback.com/webhooks"
    assert data["project_id"] == project_id
    assert "id" in data
    webhook_id = data["id"]
    
    # 2. List Webhooks
    list_response = client.get(
        f"{settings.API_V1_STR}/projects/{project_id}/webhooks"
    )
    assert list_response.status_code == 200
    webhooks = list_response.json()
    assert len(webhooks) >= 1
    assert any(w["id"] == webhook_id for w in webhooks)
    
    # 3. Update Webhook
    update_payload = {
        "url": "https://callback.com/updated",
        "trigger_type": "on_change",
        "is_active": False
    }
    update_response = client.put(
        f"{settings.API_V1_STR}/projects/{project_id}/webhooks/{webhook_id}",
        json=update_payload
    )
    assert update_response.status_code == 200
    updated_data = update_response.json()
    assert updated_data["url"] == "https://callback.com/updated"
    assert updated_data["is_active"] is False
    
    # 4. Delete Webhook
    delete_response = client.delete(
        f"{settings.API_V1_STR}/projects/{project_id}/webhooks/{webhook_id}"
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "success"
    
    # Check listing again
    list_response_after = client.get(
        f"{settings.API_V1_STR}/projects/{project_id}/webhooks"
    )
    assert not any(w["id"] == webhook_id for w in list_response_after.json())

def test_google_sheets_integration_config():
    project_id = _setup_project_for_test()
    
    # 1. Get default config (should be None or empty initially)
    get_res = client.get(
        f"{settings.API_V1_STR}/projects/{project_id}/integrations/google-sheets"
    )
    assert get_res.status_code == 200
    assert get_res.json() is None
    
    # 2. Save config
    payload = {
        "google_sheet_url": "https://docs.google.com/spreadsheets/d/12345",
        "google_sheet_sync_enabled": True
    }
    save_res = client.post(
        f"{settings.API_V1_STR}/projects/{project_id}/integrations/google-sheets",
        json=payload
    )
    assert save_res.status_code == 200
    data = save_res.json()
    assert data["google_sheet_url"] == "https://docs.google.com/spreadsheets/d/12345"
    assert data["google_sheet_sync_enabled"] is True
    
    # 3. Fetch again to check persistence
    get_res2 = client.get(
        f"{settings.API_V1_STR}/projects/{project_id}/integrations/google-sheets"
    )
    assert get_res2.status_code == 200
    data2 = get_res2.json()
    assert data2["google_sheet_url"] == "https://docs.google.com/spreadsheets/d/12345"
    assert data2["google_sheet_sync_enabled"] is True

def test_csv_export_from_cache():
    project_id = _setup_project_for_test()
    
    # Set up source and endpoint in DB
    db = TestingSessionLocal()
    try:
        source = SourceRepository(db).create(project_id, "https://hotels.com", "hotels.com")
        endpoint = ApiEndpointRepository(db).create(project_id, f"/export-hotels-{project_id[:6]}")
        db.commit()
        endpoint_id = endpoint.id
    finally:
        db.close()
        
    cached_payload = json.dumps({
        "data": [{"name": "Cache Hotel", "price": 120}, {"name": "Luxe Suites", "price": 250}],
        "metadata": {}
    })
    
    # Mock Redis client returns cached data
    mock_redis = AsyncMock()
    mock_redis.keys.return_value = []
    mock_redis.get.return_value = cached_payload
    
    async def _mock_dep():
        yield mock_redis
        
    app.dependency_overrides[runtime_router.get_redis_client] = _mock_dep
    
    try:
        response = client.get(
            f"{settings.API_V1_STR}/projects/{project_id}/export/csv"
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type")
        assert "attachment" in response.headers.get("content-disposition")
        csv_text = response.text
        assert "Cache Hotel" in csv_text
        assert "Luxe Suites" in csv_text
        assert "price" in csv_text
    finally:
        async def _no_redis():
            yield None
        app.dependency_overrides[runtime_router.get_redis_client] = _no_redis
