import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.workers.celery_tasks import refresh_endpoint_cache, dispatch_webhook_task
from app.models.entities import ApiEndpoint, Source, Schema, GeneratedExtractor, WebhookConfig, IntegrationConfig
from tests.conftest import TestingSessionLocal

def test_dispatch_webhook_success():
    with patch("app.workers.celery_tasks.httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value.status_code = 200
        mock_client.post.return_value.raise_for_status = MagicMock()
        
        res = dispatch_webhook_task.run("https://target.com", {"data": 123})
        assert res is True
        mock_client.post.assert_called_once_with("https://target.com", json={"data": 123}, timeout=10.0)

def test_refresh_endpoint_cache_drift_detection():
    db = TestingSessionLocal()
    try:
        from app.repositories.project_repo import UserRepository, ProjectRepository, SourceRepository, SchemaRepository, ExtractorRepository, ApiEndpointRepository
        # Create full structure
        user = UserRepository(db).get_by_email("test@x.com")
        if not user:
            user = UserRepository(db).create("test@x.com", "pass", "user")
        
        project = ProjectRepository(db).create(user.id, "Drift Test Project")
        source = SourceRepository(db).create(project.id, "https://hotels.com", "hotels.com")
        schema = SchemaRepository(db).create(source.id, {"properties": {"name": {"type": "string"}}})
        
        code = "async def extract(html_content, dom_tree): return [{'name': 'New Hotel'}]"
        ExtractorRepository(db).create(schema.id, code)
        
        endpoint = ApiEndpointRepository(db).create(project.id, f"/drift-hotels-{project.id[:6]}")
        
        # Create webhook
        webhook = WebhookConfig(
            project_id=project.id,
            url="https://webhook-receiver.com/drift",
            trigger_type="on_change",
            is_active=True
        )
        db.add(webhook)
        db.commit()
        
        endpoint_id = endpoint.id
    finally:
        db.close()
        
    # Mock Redis client returns an old cached payload showing different data (drift!)
    old_payload = json.dumps({
        "data": [{"name": "Old Hotel"}],
        "metadata": {}
    })
    
    mock_redis = MagicMock()
    mock_redis.get.return_value = old_payload
    
    # Mock crawl and execute sandbox
    mock_crawl = {"html": "<html></html>", "dom_tree": {}}
    mock_extracted = [{"name": "New Hotel"}]
    
    with patch("app.workers.celery_tasks.redis.from_url") as mock_redis_from_url, \
         patch("app.workers.celery_tasks.CrawlerService.crawl", new_callable=AsyncMock, return_value=mock_crawl), \
         patch("app.workers.celery_tasks.SandboxService.execute_extractor", new_callable=AsyncMock, return_value=mock_extracted), \
         patch("app.workers.celery_tasks.dispatch_webhook_task.delay") as mock_webhook_delay, \
         patch("app.workers.celery_tasks.SessionLocal", new=TestingSessionLocal):
        
        mock_redis_from_url.return_value = mock_redis
        
        res = refresh_endpoint_cache(endpoint_id)
        
        assert res is True
        # Webhook task should be called since there is data drift ("Old Hotel" != "New Hotel")
        mock_webhook_delay.assert_called_once()
        assert mock_webhook_delay.call_args[0][0] == "https://webhook-receiver.com/drift"
        assert mock_webhook_delay.call_args[0][1]["data"] == mock_extracted
