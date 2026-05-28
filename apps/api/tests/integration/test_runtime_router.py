"""
Integration tests for the runtime router (app.routers.runtime_router).

Tests:
- Authentication enforcement via X-API-KEY header
- Redis cache HIT path (returns cached data with X-Cache: HIT)
- Redis cache MISS path (crawls + extracts + caches result)
- Cache FALLBACK path on crawler failure (returns stale cache)
- Full 502 error when no cache and crawler fails
- 404 for unknown endpoint paths
- No-Redis (None) fallback still crawls and serves data
- force_refresh=true bypasses cache HIT

NOTE: get_redis_client is overridden globally via app.dependency_overrides
for every test to prevent real Redis connections from hanging the test runner.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import generate_api_key, hash_api_key
from app.repositories.project_repo import (
    UserRepository, ProjectRepository, SourceRepository,
    SchemaRepository, ExtractorRepository, ApiEndpointRepository, ApiKeyRepository,
)
from app.routers import runtime_router
from tests.conftest import TestingSessionLocal


# ─── Module-level Redis override ─────────────────────────────────────────────
# Override get_redis_client globally so NO test ever touches a real Redis server.
# Individual tests replace this with a more specific mock as needed.

async def _no_redis():
    """Default: Redis is unavailable (None)."""
    yield None

app.dependency_overrides[runtime_router.get_redis_client] = _no_redis

client = TestClient(app)


# ─── Helper ──────────────────────────────────────────────────────────────────

def _setup_full_project(raw_key: str, suffix: str = "") -> dict:
    """
    Creates a complete project stack in the test DB:
    User → Project → ApiKey → Source → Schema → Extractor → Endpoint.
    Returns a dict with IDs and the endpoint path.
    """
    db = TestingSessionLocal()
    try:
        email = f"rt_{suffix or raw_key[:8]}@test.com"
        user = UserRepository(db).create(email, "pass")
        project = ProjectRepository(db).create(user.id, "Runtime Test Project")
        ApiKeyRepository(db).create(user.id, raw_key, "Runtime Key")
        source = SourceRepository(db).create(project.id, "https://hotels.com", "hotels.com")
        schema = SchemaRepository(db).create(source.id, {"properties": {"name": {"type": "string"}}})
        code = "async def extract(html_content, dom_tree): return [{'name': 'Grand Hotel'}]"
        ExtractorRepository(db).create(schema.id, code)
        endpoint_path = f"/rt-hotels-{suffix or raw_key[:6]}"
        endpoint = ApiEndpointRepository(db).create(project.id, endpoint_path)
        db.commit()
        return {
            "user_id": user.id,
            "project_id": project.id,
            "endpoint_path": endpoint_path,
            "endpoint_id": endpoint.id,
            "raw_key": raw_key,
        }
    finally:
        db.close()


def _mock_redis(get_return=None, side_effects=None):
    """Build a configured mock Redis client as an async dependency override."""
    mock = AsyncMock()
    mock.ping.return_value = True
    if side_effects:
        mock.get.side_effect = side_effects
    else:
        mock.get.return_value = get_return

    async def _dep():
        yield mock

    return _dep, mock


# ─── Authentication Tests ─────────────────────────────────────────────────────

class TestRuntimeAuthentication:
    def test_missing_api_key_returns_422(self):
        """FastAPI returns 422 when required X-API-KEY header is absent."""
        response = client.get(f"{settings.API_V1_STR}/apis/some-path")
        assert response.status_code == 422

    def test_invalid_api_key_returns_401(self):
        response = client.get(
            f"{settings.API_V1_STR}/apis/some-path",
            headers={"X-API-KEY": "sk_live_totally_invalid_key_xyz"}
        )
        assert response.status_code == 401
        assert "Invalid or missing API key" in response.json()["detail"]

    def test_valid_key_unknown_endpoint_returns_404(self):
        raw_key, _ = generate_api_key()
        db = TestingSessionLocal()
        try:
            user = UserRepository(db).create(f"auth_{raw_key[:6]}@test.com", "pass")
            ApiKeyRepository(db).create(user.id, raw_key, "Auth Key")
            db.commit()
        finally:
            db.close()

        response = client.get(
            f"{settings.API_V1_STR}/apis/nonexistent-api-path-xyz",
            headers={"X-API-KEY": raw_key}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ─── Cache Path Tests ─────────────────────────────────────────────────────────

class TestRuntimeCachePaths:
    def test_cache_hit_returns_cached_data(self):
        """When Redis has cached data, serve it directly with X-Cache: HIT."""
        raw_key, _ = generate_api_key()
        ctx = _setup_full_project(raw_key, suffix="hit1")
        endpoint_path = ctx["endpoint_path"]
        endpoint_id = ctx["endpoint_id"]

        cached_payload = json.dumps({
            "data": [{"name": "Cached Hotel"}],
            "metadata": {
                "source_url": "https://hotels.com",
                "endpoint_id": endpoint_id,
                "cached": True,
                "extractor_version": 1,
            }
        })

        dep, _ = _mock_redis(get_return=cached_payload)
        app.dependency_overrides[runtime_router.get_redis_client] = dep

        response = client.get(
            f"{settings.API_V1_STR}/apis{endpoint_path}",
            headers={"X-API-KEY": raw_key}
        )

        app.dependency_overrides[runtime_router.get_redis_client] = _no_redis

        assert response.status_code == 200
        assert response.headers.get("X-Cache") == "HIT"
        assert response.json()["data"][0]["name"] == "Cached Hotel"

    def test_cache_miss_crawls_and_returns_data(self):
        """On a Redis miss, the router should crawl + extract and return MISS."""
        raw_key, _ = generate_api_key()
        ctx = _setup_full_project(raw_key, suffix="miss1")
        endpoint_path = ctx["endpoint_path"]

        dep, _ = _mock_redis(get_return=None)
        app.dependency_overrides[runtime_router.get_redis_client] = dep

        mock_crawl = {"html": "<html><body>Hotels</body></html>", "dom_tree": {}}
        mock_extracted = [{"name": "Grand Hotel"}]

        with patch("app.routers.runtime_router.CrawlerService.crawl", new_callable=AsyncMock, return_value=mock_crawl), \
             patch("app.routers.runtime_router.SandboxService.execute_extractor", new_callable=AsyncMock, return_value=mock_extracted):
            response = client.get(
                f"{settings.API_V1_STR}/apis{endpoint_path}",
                headers={"X-API-KEY": raw_key}
            )

        app.dependency_overrides[runtime_router.get_redis_client] = _no_redis

        assert response.status_code == 200
        assert response.headers.get("X-Cache") == "MISS"
        assert response.json()["data"][0]["name"] == "Grand Hotel"

    def test_cache_miss_writes_to_redis(self):
        """A successful MISS result must be written back to Redis via setex."""
        raw_key, _ = generate_api_key()
        ctx = _setup_full_project(raw_key, suffix="write1")
        endpoint_path = ctx["endpoint_path"]

        dep, mock_redis = _mock_redis(get_return=None)
        app.dependency_overrides[runtime_router.get_redis_client] = dep

        mock_crawl = {"html": "<html></html>", "dom_tree": {}}
        mock_extracted = [{"name": "Hotel XYZ"}]

        with patch("app.routers.runtime_router.CrawlerService.crawl", new_callable=AsyncMock, return_value=mock_crawl), \
             patch("app.routers.runtime_router.SandboxService.execute_extractor", new_callable=AsyncMock, return_value=mock_extracted):
            client.get(
                f"{settings.API_V1_STR}/apis{endpoint_path}",
                headers={"X-API-KEY": raw_key}
            )

        app.dependency_overrides[runtime_router.get_redis_client] = _no_redis

        mock_redis.setex.assert_called_once()

    def test_crawl_failure_falls_back_to_stale_cache(self):
        """When crawler fails but Redis has stale data, return stale with FALLBACK-STALE header."""
        raw_key, _ = generate_api_key()
        ctx = _setup_full_project(raw_key, suffix="stale1")
        endpoint_path = ctx["endpoint_path"]
        endpoint_id = ctx["endpoint_id"]

        stale_data = json.dumps({
            "data": [{"name": "Stale Hotel"}],
            "metadata": {
                "cached": True,
                "endpoint_id": endpoint_id,
                "source_url": "https://hotels.com",
                "extractor_version": 1,
            }
        })

        # First call (fresh check): miss; second call (fallback): stale data
        dep, _ = _mock_redis(side_effects=[None, stale_data])
        app.dependency_overrides[runtime_router.get_redis_client] = dep

        with patch("app.routers.runtime_router.CrawlerService.crawl", new_callable=AsyncMock, side_effect=Exception("Playwright timeout")):
            response = client.get(
                f"{settings.API_V1_STR}/apis{endpoint_path}",
                headers={"X-API-KEY": raw_key}
            )

        app.dependency_overrides[runtime_router.get_redis_client] = _no_redis

        assert response.status_code == 200
        assert response.headers.get("X-Cache") == "FALLBACK-STALE"
        assert response.json()["data"][0]["name"] == "Stale Hotel"

    def test_crawl_failure_no_stale_cache_returns_502(self):
        """When crawler fails AND there is no stale cache entry, return 502."""
        raw_key, _ = generate_api_key()
        ctx = _setup_full_project(raw_key, suffix="502a")
        endpoint_path = ctx["endpoint_path"]

        dep, _ = _mock_redis(side_effects=[None, None])
        app.dependency_overrides[runtime_router.get_redis_client] = dep

        with patch("app.routers.runtime_router.CrawlerService.crawl", new_callable=AsyncMock, side_effect=Exception("Network error")):
            response = client.get(
                f"{settings.API_V1_STR}/apis{endpoint_path}",
                headers={"X-API-KEY": raw_key}
            )

        app.dependency_overrides[runtime_router.get_redis_client] = _no_redis

        assert response.status_code == 502

    def test_no_redis_still_crawls_and_serves(self):
        """When Redis is unavailable (None), crawl + extract should still work."""
        raw_key, _ = generate_api_key()
        ctx = _setup_full_project(raw_key, suffix="nored1")
        endpoint_path = ctx["endpoint_path"]

        # Keep the default _no_redis override (already set globally)
        mock_crawl = {"html": "<html></html>", "dom_tree": {}}
        mock_extracted = [{"name": "No-Cache Hotel"}]

        with patch("app.routers.runtime_router.CrawlerService.crawl", new_callable=AsyncMock, return_value=mock_crawl), \
             patch("app.routers.runtime_router.SandboxService.execute_extractor", new_callable=AsyncMock, return_value=mock_extracted):
            response = client.get(
                f"{settings.API_V1_STR}/apis{endpoint_path}",
                headers={"X-API-KEY": raw_key}
            )

        assert response.status_code == 200
        assert response.json()["data"][0]["name"] == "No-Cache Hotel"

    def test_force_refresh_bypasses_cache_hit(self):
        """force_refresh=true must skip the cache HIT and re-crawl."""
        raw_key, _ = generate_api_key()
        ctx = _setup_full_project(raw_key, suffix="fref1")
        endpoint_path = ctx["endpoint_path"]
        endpoint_id = ctx["endpoint_id"]

        cached_payload = json.dumps({
            "data": [{"name": "Old Cached Data"}],
            "metadata": {
                "cached": True,
                "endpoint_id": endpoint_id,
                "source_url": "https://hotels.com",
                "extractor_version": 1,
            }
        })
        # Even though Redis would return a HIT, force_refresh=true should bypass it
        dep, _ = _mock_redis(get_return=cached_payload)
        app.dependency_overrides[runtime_router.get_redis_client] = dep

        mock_crawl = {"html": "<html></html>", "dom_tree": {}}
        mock_extracted = [{"name": "Fresh Data"}]

        with patch("app.routers.runtime_router.CrawlerService.crawl", new_callable=AsyncMock, return_value=mock_crawl), \
             patch("app.routers.runtime_router.SandboxService.execute_extractor", new_callable=AsyncMock, return_value=mock_extracted):
            response = client.get(
                f"{settings.API_V1_STR}/apis{endpoint_path}?force_refresh=true",
                headers={"X-API-KEY": raw_key}
            )

        app.dependency_overrides[runtime_router.get_redis_client] = _no_redis

        assert response.status_code == 200
        assert response.headers.get("X-Cache") == "MISS"
        assert response.json()["data"][0]["name"] == "Fresh Data"
