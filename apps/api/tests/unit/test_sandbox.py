"""
Unit tests for app.services.sandbox_service

Covers AST static analysis (verify_ast_safety) and dynamic execution
(execute_extractor) including security boundary enforcement.
"""
import pytest
from app.services.sandbox_service import SandboxService, ASTValidationError


class TestVerifyAstSafety:
    def test_allowed_safe_beautifulsoup_script(self):
        safe_code = """
import re
from bs4 import BeautifulSoup

async def extract(html_content: str, dom_tree: dict) -> list[dict]:
    soup = BeautifulSoup(html_content, 'html.parser')
    results = []
    for card in soup.find_all('div', class_='product'):
        name = card.find('h2').get_text(strip=True)
        results.append({'name': name})
    return results
"""
        # Should not raise
        SandboxService.verify_ast_safety(safe_code)

    def test_banned_import_os_raises(self):
        unsafe_code = """
import os
def extract(html, dom):
    return []
"""
        with pytest.raises(ASTValidationError) as excinfo:
            SandboxService.verify_ast_safety(unsafe_code)
        assert "Unsafe import detected" in str(excinfo.value)

    def test_banned_import_from_subprocess_raises(self):
        unsafe_code = """
from subprocess import Popen
def extract(html, dom):
    return []
"""
        with pytest.raises(ASTValidationError) as excinfo:
            SandboxService.verify_ast_safety(unsafe_code)
        assert "Unsafe import detected" in str(excinfo.value)

    def test_banned_function_eval_raises(self):
        unsafe_code = """
def extract(html, dom):
    eval("print('hack')")
    return []
"""
        with pytest.raises(ASTValidationError) as excinfo:
            SandboxService.verify_ast_safety(unsafe_code)
        assert "Unsafe function call detected" in str(excinfo.value)

    def test_banned_function_open_raises(self):
        unsafe_code = """
def extract(html, dom):
    with open('/etc/passwd', 'r') as f:
        pass
    return []
"""
        with pytest.raises(ASTValidationError) as excinfo:
            SandboxService.verify_ast_safety(unsafe_code)
        assert "Unsafe function call detected" in str(excinfo.value)

    def test_banned_import_sys_raises(self):
        unsafe_code = """
import sys
async def extract(html, dom):
    return []
"""
        with pytest.raises(ASTValidationError) as excinfo:
            SandboxService.verify_ast_safety(unsafe_code)
        assert "Unsafe import detected" in str(excinfo.value)

    def test_allowed_import_json(self):
        safe_code = """
import json
async def extract(html_content: str, dom_tree: dict) -> list[dict]:
    return [json.loads('{"name": "test"}')]
"""
        # Should not raise
        SandboxService.verify_ast_safety(safe_code)

    def test_allowed_import_re(self):
        safe_code = """
import re
async def extract(html_content: str, dom_tree: dict) -> list[dict]:
    return [{"match": re.search(r'test', html_content).group()}]
"""
        SandboxService.verify_ast_safety(safe_code)


class TestSandboxExecution:
    @pytest.mark.asyncio
    async def test_execution_success(self):
        safe_code = """
async def extract(html, dom):
    return [{"title": "Sea Resort", "price": 120.0}]
"""
        result = await SandboxService.execute_extractor(safe_code, "<html></html>", {})
        assert len(result) == 1
        assert result[0]["title"] == "Sea Resort"
        assert result[0]["price"] == 120.0

    @pytest.mark.asyncio
    async def test_execution_missing_extract_entrypoint_raises(self):
        invalid_code = """
def parse_page(html, dom):
    return []
"""
        with pytest.raises(Exception) as excinfo:
            await SandboxService.execute_extractor(invalid_code, "<html></html>", {})
        assert "does not define an 'extract' function" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_execution_returns_list_of_dicts(self):
        code = """
async def extract(html, dom):
    return [{"a": 1}, {"a": 2}, {"a": 3}]
"""
        result = await SandboxService.execute_extractor(code, "<html></html>", {})
        assert isinstance(result, list)
        assert all(isinstance(item, dict) for item in result)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_execution_with_beautifulsoup(self):
        html = "<html><body><div class='item'><h2>Hotel Alpha</h2></div></body></html>"
        code = """
from bs4 import BeautifulSoup
async def extract(html_content, dom_tree):
    soup = BeautifulSoup(html_content, 'html.parser')
    return [{'name': h.get_text(strip=True)} for h in soup.find_all('h2')]
"""
        result = await SandboxService.execute_extractor(code, html, {})
        assert result[0]["name"] == "Hotel Alpha"
