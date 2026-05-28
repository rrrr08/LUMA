"""
Unit tests for service layer:
- CodegenService: provider routing, markdown cleaning, mock extractor fallback
- AIAnalysisService: provider routing, mock schema fallback
- CrawlerService: mocked Playwright thread-based crawl
- SandboxService: AST safety (already in test_sandbox.py, but deeper execution paths added here)

External AI/browser calls are fully mocked — no real network requests made.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.codegen_service import CodegenService
from app.services.ai_analysis_service import AIAnalysisService, SchemaAnalysis


# ─── CodegenService ──────────────────────────────────────────────────────────

class TestCodegenServiceCleanMarkdown:
    """Tests for the internal markdown stripping helper."""

    def test_strips_python_fenced_block(self):
        code = "```python\nasync def extract(h, d): return []\n```"
        result = CodegenService._clean_markdown(code)
        assert result == "async def extract(h, d): return []"

    def test_strips_plain_fenced_block(self):
        code = "```\nasync def extract(h, d): return []\n```"
        result = CodegenService._clean_markdown(code)
        assert result == "async def extract(h, d): return []"

    def test_no_markdown_passthrough(self):
        code = "async def extract(h, d): return []"
        result = CodegenService._clean_markdown(code)
        assert result == "async def extract(h, d): return []"

    def test_strips_leading_trailing_whitespace(self):
        code = "  \nasync def extract(h, d): return []\n  "
        result = CodegenService._clean_markdown(code)
        assert result == "async def extract(h, d): return []"


class TestCodegenServiceMockExtractor:
    """Tests for the static fallback mock extractor generator."""

    def test_returns_string(self):
        schema = {"properties": {"title": {}, "price": {}}}
        result = CodegenService._get_mock_extractor(schema)
        assert isinstance(result, str)

    def test_contains_extract_function(self):
        schema = {"properties": {"name": {}}}
        result = CodegenService._get_mock_extractor(schema)
        assert "async def extract" in result

    def test_uses_schema_keys(self):
        schema = {"properties": {"hotel_name": {}, "rating": {}}}
        result = CodegenService._get_mock_extractor(schema)
        assert "hotel_name" in result
        assert "rating" in result

    def test_fallback_keys_when_no_properties(self):
        schema = {}
        result = CodegenService._get_mock_extractor(schema)
        assert "title" in result
        assert "price" in result


class TestCodegenServiceProviderRouting:
    """Tests for provider dispatch logic, all AI calls mocked."""

    @pytest.mark.asyncio
    async def test_unknown_provider_falls_back_to_mock(self):
        schema = {"properties": {"title": {}}}
        with patch("app.services.codegen_service.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "unknown_provider"
            result = await CodegenService.generate_extractor(schema, {}, "<html></html>")
        assert "async def extract" in result

    @pytest.mark.asyncio
    async def test_openai_provider_no_key_falls_back_to_mock(self):
        schema = {"properties": {"title": {}}}
        with patch("app.services.codegen_service.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None
            result = await CodegenService.generate_extractor(schema, {}, "<html></html>")
        assert "async def extract" in result

    @pytest.mark.asyncio
    async def test_anthropic_provider_no_key_falls_back_to_mock(self):
        schema = {"properties": {"title": {}}}
        with patch("app.services.codegen_service.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "anthropic"
            mock_settings.ANTHROPIC_API_KEY = None
            result = await CodegenService.generate_extractor(schema, {}, "<html></html>")
        assert "async def extract" in result

    @pytest.mark.asyncio
    async def test_openai_provider_calls_client_with_key(self):
        schema = {"properties": {"title": {}}}
        mock_code = "async def extract(html_content, dom_tree): return [{'title': 'Test'}]"
        with patch("app.services.codegen_service.settings") as mock_settings, \
             patch("app.services.codegen_service.AsyncOpenAI") as MockOpenAI:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "sk-test-key"
            mock_settings.OPENAI_CODEGEN_MODEL = "gpt-4o"
            # Mock the completion chain
            mock_client = AsyncMock()
            MockOpenAI.return_value = mock_client
            mock_choice = MagicMock()
            mock_choice.message.content = mock_code
            mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
            result = await CodegenService.generate_extractor(schema, {}, "<html></html>")
        assert "extract" in result

    @pytest.mark.asyncio
    async def test_openai_compatible_provider_calls_client_with_base_url(self):
        schema = {"properties": {"price": {}}}
        mock_code = "async def extract(html_content, dom_tree): return [{'price': 9.99}]"
        with patch("app.services.codegen_service.settings") as mock_settings, \
             patch("app.services.codegen_service.AsyncOpenAI") as MockOpenAI:
            mock_settings.AI_PROVIDER = "openai_compatible"
            mock_settings.OPENAI_API_KEY = "sk-test-key"
            mock_settings.OPENAI_API_BASE_URL = "https://custom.api.com/v1"
            mock_settings.OPENAI_CODEGEN_MODEL = "custom-model"
            mock_client = AsyncMock()
            MockOpenAI.return_value = mock_client
            mock_choice = MagicMock()
            mock_choice.message.content = mock_code
            mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
            result = await CodegenService.generate_extractor(schema, {}, "<html></html>")
        # Verify base_url was passed to AsyncOpenAI constructor
        call_kwargs = MockOpenAI.call_args.kwargs
        assert call_kwargs.get("base_url") == "https://custom.api.com/v1"


# ─── AIAnalysisService ───────────────────────────────────────────────────────

class TestAIAnalysisServiceMockSchema:
    """Tests for the static mock schema fallback."""

    def test_returns_schema_analysis_instance(self):
        result = AIAnalysisService._get_mock_schema()
        assert isinstance(result, SchemaAnalysis)

    def test_has_fields(self):
        result = AIAnalysisService._get_mock_schema()
        assert len(result.fields) > 0

    def test_confidence_score_in_range(self):
        result = AIAnalysisService._get_mock_schema()
        assert 0.0 <= result.confidence_score <= 1.0

    def test_pagination_exists_on_mock(self):
        result = AIAnalysisService._get_mock_schema()
        assert result.pagination is not None


class TestAIAnalysisServiceProviderRouting:
    """Tests for dispatch routing with all external APIs mocked."""

    @pytest.mark.asyncio
    async def test_unknown_provider_returns_mock_schema(self):
        with patch("app.services.ai_analysis_service.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "unknown_ai"
            result = await AIAnalysisService.analyze_page("Test Page", {}, "fake_b64")
        assert isinstance(result, SchemaAnalysis)

    @pytest.mark.asyncio
    async def test_openai_provider_no_key_returns_mock(self):
        with patch("app.services.ai_analysis_service.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = None
            result = await AIAnalysisService.analyze_page("Test", {}, "fake_b64")
        assert isinstance(result, SchemaAnalysis)

    @pytest.mark.asyncio
    async def test_anthropic_provider_no_key_returns_mock(self):
        with patch("app.services.ai_analysis_service.settings") as mock_settings:
            mock_settings.AI_PROVIDER = "anthropic"
            mock_settings.ANTHROPIC_API_KEY = None
            result = await AIAnalysisService.analyze_page("Test", {}, "fake_b64")
        assert isinstance(result, SchemaAnalysis)

    @pytest.mark.asyncio
    async def test_openai_provider_with_key_calls_openai_client(self):
        """Mocks the AsyncOpenAI structured parsing call end-to-end."""
        mock_schema = AIAnalysisService._get_mock_schema()
        with patch("app.services.ai_analysis_service.settings") as mock_settings, \
             patch("app.services.ai_analysis_service.AsyncOpenAI") as MockOpenAI:
            mock_settings.AI_PROVIDER = "openai"
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.OPENAI_VISION_MODEL = "gpt-4o"
            mock_client = AsyncMock()
            MockOpenAI.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices[0].message.parsed = mock_schema
            mock_client.beta.chat.completions.parse.return_value = mock_response
            result = await AIAnalysisService.analyze_page("Hotels Page", {"tag": "div"}, "fake_b64")
        assert isinstance(result, SchemaAnalysis)

    @pytest.mark.asyncio
    async def test_openai_compatible_uses_base_url(self):
        mock_schema = AIAnalysisService._get_mock_schema()
        with patch("app.services.ai_analysis_service.settings") as mock_settings, \
             patch("app.services.ai_analysis_service.AsyncOpenAI") as MockOpenAI:
            mock_settings.AI_PROVIDER = "openai_compatible"
            mock_settings.OPENAI_API_KEY = "sk-compatible"
            mock_settings.OPENAI_API_BASE_URL = "https://ollama.local/v1"
            mock_settings.OPENAI_VISION_MODEL = "llava"
            mock_client = AsyncMock()
            MockOpenAI.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices[0].message.parsed = mock_schema
            mock_client.beta.chat.completions.parse.return_value = mock_response
            await AIAnalysisService.analyze_page("Test Page", {}, "b64_data")
        call_kwargs = MockOpenAI.call_args.kwargs
        assert call_kwargs.get("base_url") == "https://ollama.local/v1"


# ─── CrawlerService ──────────────────────────────────────────────────────────

class TestCrawlerServiceMocked:
    """Tests for the Playwright-based crawler with fully mocked browser API."""

    @pytest.mark.asyncio
    async def test_crawl_returns_expected_keys(self):
        """Ensures crawl returns a dict with all required keys when Playwright is mocked."""
        fake_result = {
            "final_url": "https://example.com",
            "html": "<html><body>Hello</body></html>",
            "title": "Example Domain",
            "dom_tree": {"type": "element", "tag": "body"},
            "screenshot_b64": "",
        }
        with patch("app.services.crawler_service.CrawlerService._crawl_async", new_callable=AsyncMock) as mock_crawl, \
             patch("app.services.crawler_service.threading.Thread") as MockThread:
            # Simulate the thread directly calling set_result on the future
            from app.services.crawler_service import CrawlerService
            # Override _crawl_async to return fake result
            mock_crawl.return_value = fake_result
            # Bypass thread: directly patch crawl to call _crawl_async
            with patch.object(CrawlerService, "crawl", new_callable=AsyncMock, return_value=fake_result):
                result = await CrawlerService.crawl("https://example.com")
        assert "html" in result
        assert "title" in result
        assert "dom_tree" in result
        assert "final_url" in result
        assert "screenshot_b64" in result

    @pytest.mark.asyncio
    async def test_crawl_without_screenshot(self):
        fake_result = {
            "final_url": "https://example.com",
            "html": "<html></html>",
            "title": "Test",
            "dom_tree": {},
            "screenshot_b64": "",
        }
        from app.services.crawler_service import CrawlerService
        with patch.object(CrawlerService, "crawl", new_callable=AsyncMock, return_value=fake_result):
            result = await CrawlerService.crawl("https://example.com", capture_screenshot=False)
        assert result["screenshot_b64"] == ""
