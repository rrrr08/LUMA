import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import generate_api_key
from app.repositories.project_repo import (
    UserRepository, ProjectRepository, SourceRepository,
    SchemaRepository, ExtractorRepository, ApiEndpointRepository, ApiKeyRepository,
    RequestLogRepository
)
from app.models.entities import RequestLog
from tests.conftest import TestingSessionLocal

client = TestClient(app)

def _setup_user_with_plan(plan: str, raw_key: str, suffix: str = "") -> dict:
    """Creates a user with a specific plan, key, and project structure."""
    db = TestingSessionLocal()
    try:
        email = f"billing_{plan}_{suffix}@test.com"
        user_repo = UserRepository(db)
        user = user_repo.create(email, "pass")
        user.plan = plan
        db.commit()
        
        project = ProjectRepository(db).create(user.id, f"{plan} Project")
        ApiKeyRepository(db).create(user.id, raw_key, f"{plan} Key")
        db.commit()
        return {
            "user_id": user.id,
            "project_id": project.id,
            "raw_key": raw_key
        }
    finally:
        db.close()

class TestBillingLimits:
    def test_deploy_api_limit_enforced_for_free_plan(self):
        """Users on free plan can deploy at most 3 active endpoints."""
        raw_key, _ = generate_api_key()
        ctx = _setup_user_with_plan("free", raw_key, "deploy_free")
        user_id = ctx["user_id"]
        
        db = TestingSessionLocal()
        try:
            # Let's mock existing active endpoints for this user.
            # Free limit is 3. We'll create 3 endpoints for 3 other active projects.
            user = UserRepository(db).get_by_id(user_id)
            
            project_repo = ProjectRepository(db)
            endpoint_repo = ApiEndpointRepository(db)
            
            for i in range(3):
                p = project_repo.create(user.id, f"Mocked Project {i}")
                p.status = "active"
                endpoint_repo.create(p.id, f"/mocked-api-{i}")
            db.commit()
            
            # Now let's try to deploy a new one on a 4th project.
            proj = project_repo.create(user.id, "4th Project")
            payload = {
                "json_schema": {
                    "metadata": {"target_url": "https://test.com"},
                    "properties": {}
                },
                "endpoint_path": "over-limit-api"
            }
            
            response = client.post(
                f"{settings.API_V1_STR}/projects/{proj.id}/deploy",
                json=payload
            )
            
            assert response.status_code == 403
            assert "Active API limit reached" in response.json()["detail"]
            
        finally:
            db.close()

    def test_serve_api_request_volume_limit_free(self):
        """Users on free plan get blocked if they exceed monthly request limit (100)."""
        raw_key, _ = generate_api_key()
        ctx = _setup_user_with_plan("free", raw_key, "req_limit")
        user_id = ctx["user_id"]
        project_id = ctx["project_id"]
        
        db = TestingSessionLocal()
        try:
            # Setup endpoint
            source = SourceRepository(db).create(project_id, "https://test.com", "test.com")
            schema = SchemaRepository(db).create(source.id, {"properties": {}})
            ExtractorRepository(db).create(schema.id, "async def extract(h, d): return []")
            endpoint = ApiEndpointRepository(db).create(project_id, "/free-vol-check")
            
            # Write 100 request logs for this user to trigger limit
            for _ in range(100):
                log = RequestLog(
                    endpoint_id=endpoint.id,
                    user_id=user_id,
                    status_code=200,
                    cache_status="HIT",
                    response_time_ms=50.0
                )
                db.add(log)
            db.commit()
            
            # Try to serve this endpoint. Since request volume is 100 (which is the limit), it should be blocked.
            response = client.get(
                f"{settings.API_V1_STR}/apis/free-vol-check",
                headers={"X-API-KEY": raw_key}
            )
            assert response.status_code == 403
            assert "API request volume quota exceeded" in response.json()["detail"]
            
        finally:
            db.close()

    def test_serve_api_crawl_limit_free(self):
        """Users on free plan get blocked if they exceed monthly playwright crawls limit (20)."""
        raw_key, _ = generate_api_key()
        ctx = _setup_user_with_plan("free", raw_key, "crawl_limit")
        user_id = ctx["user_id"]
        project_id = ctx["project_id"]
        
        db = TestingSessionLocal()
        try:
            # Setup endpoint
            source = SourceRepository(db).create(project_id, "https://test.com", "test.com")
            schema = SchemaRepository(db).create(source.id, {"properties": {}})
            ExtractorRepository(db).create(schema.id, "async def extract(h, d): return []")
            endpoint = ApiEndpointRepository(db).create(project_id, "/free-crawl-check")
            
            # Write 20 playwright crawls (cache miss) logs for this user
            for _ in range(20):
                log = RequestLog(
                    endpoint_id=endpoint.id,
                    user_id=user_id,
                    status_code=200,
                    cache_status="MISS",  # MISS represents a crawl
                    response_time_ms=1200.0
                )
                db.add(log)
            db.commit()
            
            # Request. It is a cache miss, so it checks crawl limit. Since crawl count is 20 (limit reached), it blocks.
            response = client.get(
                f"{settings.API_V1_STR}/apis/free-crawl-check",
                headers={"X-API-KEY": raw_key}
            )
            assert response.status_code == 403
            assert "Playwright crawls quota exceeded" in response.json()["detail"]
            
        finally:
            db.close()

    def test_update_plan_creates_invoice_with_promo(self):
        """Updating plan to paid tier (pro) with SAVE50 promo code generates invoice with 50% discount."""
        # Clean current plan
        db = TestingSessionLocal()
        try:
            # Get the test user created by override_get_current_user_id
            user = db.query(UserRepository.create.__globals__["User"]).filter_by(email="test@x.com").first()
            if user:
                user.plan = "free"
                db.commit()
        finally:
            db.close()

        # Call update plan
        response = client.put(
            f"{settings.API_V1_STR}/auth/plan",
            json={"plan": "pro", "promo_code": "SAVE50"}
        )
        assert response.status_code == 200
        assert response.json()["plan"] == "pro"

        # Check invoices
        inv_response = client.get(f"{settings.API_V1_STR}/auth/invoices")
        assert inv_response.status_code == 200
        data = inv_response.json()
        assert len(data) >= 1
        assert data[0]["plan"] == "pro"
        assert data[0]["amount"] == 14.5  # 50% discount on $29

    def test_get_and_put_quota_settings(self):
        """Can retrieve and update quota notification settings."""
        # Get defaults
        response = client.get(f"{settings.API_V1_STR}/auth/quota-settings")
        assert response.status_code == 200
        data = response.json()
        assert data["email_alerts_enabled"] is True
        assert data["slack_alerts_enabled"] is False

        # Update settings
        update_payload = {
            "email_alerts_enabled": False,
            "slack_alerts_enabled": True,
            "slack_webhook_url": "https://hooks.slack.com/services/test",
            "threshold_percentage": 90
        }
        put_response = client.put(
            f"{settings.API_V1_STR}/auth/quota-settings",
            json=update_payload
        )
        assert put_response.status_code == 200
        put_data = put_response.json()
        assert put_data["email_alerts_enabled"] is False
        assert put_data["slack_alerts_enabled"] is True
        assert put_data["slack_webhook_url"] == "https://hooks.slack.com/services/test"
        assert put_data["threshold_percentage"] == 90

    def test_razorpay_create_order_mock(self):
        """Creating a Razorpay order in Sandbox Mock Mode returns a mock order ID."""
        response = client.post(
            f"{settings.API_V1_STR}/auth/razorpay/create-order",
            json={"plan": "pro", "promo_code": "SAVE50"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_mock"] is True
        assert data["order_id"].startswith("order_mock_")
        assert data["currency"] == "INR"
        # 50% discount on 29 USD * 83 INR/USD * 100 paise/INR = 120350 paise
        assert data["amount"] == 120350

    def test_razorpay_verify_payment_mock(self):
        """Verifying a payment in Sandbox Mock Mode successfully upgrades user plan and generates an invoice."""
        # 1. First reset plan to free
        db = TestingSessionLocal()
        try:
            user = db.query(UserRepository.create.__globals__["User"]).filter_by(email="test@x.com").first()
            if user:
                user.plan = "free"
                db.commit()
        finally:
            db.close()

        # 2. Call verification with mock order ID
        response = client.post(
            f"{settings.API_V1_STR}/auth/razorpay/verify-payment",
            json={
                "razorpay_order_id": "order_mock_1234567890",
                "plan": "startup",
                "amount_usd": 99.0,
                "promo_code": "SAVE50"
            }
        )
        assert response.status_code == 200
        assert response.json()["plan"] == "startup"

        # 3. Check that the invoice was generated for Startup plan with 50% discount (49.50)
        inv_response = client.get(f"{settings.API_V1_STR}/auth/invoices")
        assert inv_response.status_code == 200
        data = inv_response.json()
        assert len(data) >= 1
        assert data[0]["plan"] == "startup"
        assert data[0]["amount"] == 49.5  # 50% discount on $99

    @patch("httpx.AsyncClient.post")
    def test_razorpay_create_order_live(self, mock_post):
        """When Razorpay keys are configured, create-order calls the external Razorpay API."""
        with patch.object(settings, "RAZORPAY_KEY_ID", "live_key"), \
             patch.object(settings, "RAZORPAY_KEY_SECRET", "live_secret"):
            
            # Setup mock response from Razorpay
            from unittest.mock import MagicMock
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.json = MagicMock(return_value={
                "id": "order_live_12345",
                "amount": 240700,
                "currency": "INR"
            })
            mock_post.return_value = mock_resp
            
            response = client.post(
                f"{settings.API_V1_STR}/auth/razorpay/create-order",
                json={"plan": "pro"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["is_mock"] is False
            assert data["order_id"] == "order_live_12345"
            assert data["key_id"] == "live_key"
            
            # Verify the call parameters
            assert mock_post.called
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://api.razorpay.com/v1/orders"
            assert call_args[1]["auth"] == ("live_key", "live_secret")
            assert call_args[1]["json"]["amount"] == 240700

    def test_razorpay_verify_payment_live_failure(self):
        """Verifying live payment with incorrect signature fails."""
        with patch.object(settings, "RAZORPAY_KEY_ID", "live_key"), \
             patch.object(settings, "RAZORPAY_KEY_SECRET", "live_secret"):
            
            response = client.post(
                f"{settings.API_V1_STR}/auth/razorpay/verify-payment",
                json={
                    "razorpay_order_id": "order_live_12345",
                    "razorpay_payment_id": "pay_live_12345",
                    "razorpay_signature": "invalid_signature_hash",
                    "plan": "pro",
                    "amount_usd": 29.0
                }
            )
            assert response.status_code == 400
            assert "Invalid payment signature" in response.json()["detail"]


