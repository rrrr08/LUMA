"""
Integration tests for the project management router (app.routers.project_router).

All external service calls (crawl, AI analysis, codegen, sandbox) are mocked.
The test DB is an in-memory SQLite provided by conftest.py.
"""
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


class TestProjectCRUD:
    """Tests for project create and list endpoints."""

    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_create_project_success(self):
        response = client.post(
            f"{settings.API_V1_STR}/projects",
            json={"name": "Integration Test Project"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Integration Test Project"
        assert "id" in data

    def test_create_project_returns_project_response_fields(self):
        response = client.post(
            f"{settings.API_V1_STR}/projects",
            json={"name": "Schema Fields Test"}
        )
        data = response.json()
        assert "id" in data
        assert "user_id" in data
        assert "name" in data
        assert "status" in data

    def test_get_projects_list_returns_list(self):
        # Create at least one project first
        client.post(f"{settings.API_V1_STR}/projects", json={"name": "List Test"})
        response = client.get(f"{settings.API_V1_STR}/projects")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_projects_list_contains_created_project(self):
        project_name = "Unique Project For Listing Test"
        client.post(f"{settings.API_V1_STR}/projects", json={"name": project_name})
        response = client.get(f"{settings.API_V1_STR}/projects")
        names = [p["name"] for p in response.json()]
        assert project_name in names


class TestApiKeyManagement:
    """Tests for API key creation and listing endpoints."""

    def test_create_api_key_success(self):
        response = client.post(
            f"{settings.API_V1_STR}/projects/keys",
            json={"name": "My Test Key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "raw_key" in data
        assert data["raw_key"].startswith("sk_live_")
        assert data["name"] == "My Test Key"

    def test_create_api_key_returns_id_and_name(self):
        response = client.post(
            f"{settings.API_V1_STR}/projects/keys",
            json={"name": "Key With ID Check"}
        )
        data = response.json()
        assert "id" in data
        assert "created_at" in data

    def test_list_api_keys(self):
        # Create a key first
        client.post(f"{settings.API_V1_STR}/projects/keys", json={"name": "Listing Key"})
        response = client.get(f"{settings.API_V1_STR}/projects/keys")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    def test_raw_key_only_shown_on_creation(self):
        """The list endpoint returns ApiKeyResponse which has no raw_key field."""
        client.post(f"{settings.API_V1_STR}/projects/keys", json={"name": "Hidden Key"})
        response = client.get(f"{settings.API_V1_STR}/projects/keys")
        keys = response.json()
        for k in keys:
            assert "raw_key" not in k


class TestCrawlEndpoint:
    """Tests for POST /projects/crawl with mocked CrawlerService."""

    def test_crawl_success(self):
        mock_result = {
            "title": "Hotels Page",
            "final_url": "https://hotels.com",
            "html": "<html><body>Hotels</body></html>",
            "screenshot_b64": "abc123=",
            "dom_tree": {"type": "element", "tag": "body"},
        }
        with patch("app.routers.project_router.CrawlerService.crawl", new_callable=AsyncMock) as mock_crawl:
            mock_crawl.return_value = mock_result
            response = client.post(
                f"{settings.API_V1_STR}/projects/crawl",
                json={"url": "https://hotels.com"}
            )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Hotels Page"
        assert data["final_url"] == "https://hotels.com"
        assert data["html_length"] > 0

    def test_crawl_failure_returns_502(self):
        with patch("app.routers.project_router.CrawlerService.crawl", new_callable=AsyncMock) as mock_crawl:
            mock_crawl.side_effect = Exception("Network unreachable")
            response = client.post(
                f"{settings.API_V1_STR}/projects/crawl",
                json={"url": "https://broken-site.com"}
            )
        assert response.status_code == 502
        assert "Crawling failed" in response.json()["detail"]


class TestAnalyzeVisualsEndpoint:
    """Tests for POST /projects/analyze-visuals with mocked AIAnalysisService."""

    def test_analyze_visuals_success(self):
        from app.services.ai_analysis_service import AIAnalysisService
        mock_schema = AIAnalysisService._get_mock_schema()
        with patch("app.routers.project_router.AIAnalysisService.analyze_page", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_schema
            response = client.post(
                f"{settings.API_V1_STR}/projects/analyze-visuals",
                json={
                    "title": "Hotels",
                    "dom_tree": {"tag": "div"},
                    "screenshot_b64": "abc_base64_data"
                }
            )
        assert response.status_code == 200
        data = response.json()
        assert "page_type" in data
        assert "fields" in data

    def test_analyze_visuals_missing_screenshot_returns_400(self):
        response = client.post(
            f"{settings.API_V1_STR}/projects/analyze-visuals",
            json={"title": "Test", "dom_tree": {}, "screenshot_b64": ""}
        )
        assert response.status_code == 400

    def test_analyze_visuals_ai_failure_returns_500(self):
        with patch("app.routers.project_router.AIAnalysisService.analyze_page", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.side_effect = Exception("AI service unavailable")
            response = client.post(
                f"{settings.API_V1_STR}/projects/analyze-visuals",
                json={"title": "Fail Test", "dom_tree": {}, "screenshot_b64": "fake_b64"}
            )
        assert response.status_code == 500


class TestProjectSchemaEndpoint:
    """Tests for GET /projects/{project_id}/schema."""

    def test_schema_for_unknown_project_returns_404(self):
        response = client.get(f"{settings.API_V1_STR}/projects/nonexistent-project-id/schema")
        assert response.status_code == 404

    def test_schema_for_project_without_source_returns_404(self):
        # Create a project but do not set up source/schema
        create_resp = client.post(
            f"{settings.API_V1_STR}/projects",
            json={"name": "Schema-less Project"}
        )
        project_id = create_resp.json()["id"]
        response = client.get(f"{settings.API_V1_STR}/projects/{project_id}/schema")
        assert response.status_code == 404


class TestDeployEndpoint:
    """Tests for POST /projects/{project_id}/deploy — mocks crawl, codegen, sandbox."""

    def _create_project(self):
        resp = client.post(
            f"{settings.API_V1_STR}/projects",
            json={"name": "Deploy Test Project"}
        )
        return resp.json()["id"]

    def test_deploy_missing_project_returns_404(self):
        payload = {
            "json_schema": {"metadata": {"target_url": "https://test.com"}},
            "endpoint_path": "test-api"
        }
        response = client.post(
            f"{settings.API_V1_STR}/projects/nonexistent-id/deploy",
            json=payload
        )
        assert response.status_code == 404

    def test_deploy_missing_target_url_returns_400(self):
        project_id = self._create_project()
        payload = {
            "json_schema": {"metadata": {}},
            "endpoint_path": "missing-url"
        }
        response = client.post(
            f"{settings.API_V1_STR}/projects/{project_id}/deploy",
            json=payload
        )
        assert response.status_code == 400

    def test_deploy_success(self):
        """Full deploy flow with mocked crawl, codegen, and sandbox."""
        project_id = self._create_project()
        mock_crawl_result = {
            "title": "Hotels",
            "final_url": "https://hotels.com",
            "html": "<html><body><div class='hotel'>Grand Hotel</div></body></html>",
            "screenshot_b64": "",
            "dom_tree": {"type": "element", "tag": "body"},
        }
        mock_code = """
async def extract(html_content: str, dom_tree: dict) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    return [{"name": h.get_text(strip=True)} for h in soup.find_all(class_='hotel')]
"""
        mock_extracted = [{"name": "Grand Hotel"}]
        with patch("app.routers.project_router.CrawlerService.crawl", new_callable=AsyncMock, return_value=mock_crawl_result), \
             patch("app.routers.project_router.CodegenService.generate_extractor", new_callable=AsyncMock, return_value=mock_code), \
             patch("app.routers.project_router.SandboxService.execute_extractor", new_callable=AsyncMock, return_value=mock_extracted):
            payload = {
                "json_schema": {
                    "metadata": {"target_url": "https://hotels.com"},
                    "properties": {"name": {"type": "string"}}
                },
                "endpoint_path": "hotels-api"
            }
            response = client.post(
                f"{settings.API_V1_STR}/projects/{project_id}/deploy",
                json=payload
            )
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "/hotels-api"
        assert data["project_id"] == project_id

    def test_deploy_sandbox_failure_returns_422(self):
        """Sandbox failure should bubble up as 422 Unprocessable Entity."""
        project_id = self._create_project()
        mock_crawl_result = {
            "title": "Bad Site",
            "final_url": "https://bad.com",
            "html": "<html></html>",
            "screenshot_b64": "",
            "dom_tree": {},
        }
        with patch("app.routers.project_router.CrawlerService.crawl", new_callable=AsyncMock, return_value=mock_crawl_result), \
             patch("app.routers.project_router.CodegenService.generate_extractor", new_callable=AsyncMock, return_value="async def extract(h, d): raise Exception('parse error')"), \
             patch("app.routers.project_router.SandboxService.execute_extractor", new_callable=AsyncMock, side_effect=Exception("Sandbox execution failed")):
            payload = {
                "json_schema": {
                    "metadata": {"target_url": "https://bad.com"},
                    "properties": {}
                },
                "endpoint_path": "bad-api"
            }
            response = client.post(
                f"{settings.API_V1_STR}/projects/{project_id}/deploy",
                json=payload
            )
        assert response.status_code == 422
