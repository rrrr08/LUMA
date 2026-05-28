import logging
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

class CodegenService:
    @classmethod
    async def generate_extractor(
        cls,
        target_schema: dict,
        dom_tree_sample: dict,
        html_sample: str
    ) -> str:
        """
        Main entrypoint. Dispatches code generation to the configured AI provider.
        """
        provider = settings.AI_PROVIDER.lower()
        logger.info(f"Dispatching code generation to provider: {provider}")
        
        if provider == "openai":
            return await cls._generate_openai(target_schema, dom_tree_sample, html_sample)
        elif provider == "openai_compatible":
            return await cls._generate_openai_compatible(target_schema, dom_tree_sample, html_sample)
        elif provider == "anthropic":
            return await cls._generate_anthropic(target_schema, dom_tree_sample, html_sample)
        else:
            logger.warning(f"Unknown AI Provider '{provider}'. Falling back to Mock Extractor.")
            return cls._get_mock_extractor(target_schema)

    @classmethod
    async def _generate_openai(
        cls,
        target_schema: dict,
        dom_tree_sample: dict,
        html_sample: str
    ) -> str:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not configured. Returning fallback mock extractor code.")
            return cls._get_mock_extractor(target_schema)
            
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return await cls._call_openai_codegen(client, settings.OPENAI_CODEGEN_MODEL, target_schema, dom_tree_sample, html_sample)

    @classmethod
    async def _generate_openai_compatible(
        cls,
        target_schema: dict,
        dom_tree_sample: dict,
        html_sample: str
    ) -> str:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not configured. Returning fallback mock extractor code.")
            return cls._get_mock_extractor(target_schema)
            
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE_URL
        )
        return await cls._call_openai_codegen(client, settings.OPENAI_CODEGEN_MODEL, target_schema, dom_tree_sample, html_sample)

    @staticmethod
    async def _call_openai_codegen(
        client: AsyncOpenAI,
        model: str,
        target_schema: dict,
        dom_tree_sample: dict,
        html_sample: str
    ) -> str:
        # Extract body to ignore headers, and increase snippet size to 40k chars
        from bs4 import BeautifulSoup
        import json
        try:
            soup = BeautifulSoup(html_sample, 'lxml')
            body_element = soup.body
            html_str = str(body_element)[:40000] if body_element else html_sample[:40000]
        except Exception:
            html_str = html_sample[:40000]
        dom_str = json.dumps(dom_tree_sample)[:40000]
        
        prompt = (
            f"You are a master python engineer specialized in writing extremely resilient web scraping code.\n"
            f"Write a Python parsing script that extracts items matching a specified JSON schema from raw HTML.\n\n"
            f"Target Schema:\n{target_schema}\n\n"
            f"Simplified Visual DOM Tree snippet:\n{dom_str}\n\n"
            f"Raw HTML sample:\n{html_str}\n\n"
            f"Strict Constraints:\n"
            f"1. You MUST define a single asynchronous entrypoint: `async def extract(html_content: str, dom_tree: dict) -> list[dict]:`\n"
            f"2. Do NOT import or use any banned modules: 'os', 'sys', 'subprocess', 'socket', 'shutil', 'importlib', 'requests', 'httpx', 'urllib'.\n"
            f"3. You CAN import 'bs4' (BeautifulSoup), 'lxml', 'json', 're', 'datetime'.\n"
            f"4. You must NOT perform any local filesystem reads or writes (e.g. no 'open()').\n"
            f"5. The function must return a list of dictionaries matching the keys and types in the Target Schema.\n"
            f"6. Make selectors resilient by using fallback classes or tag structures where possible.\n"
            f"7. Return ONLY the raw Python code blocks, with no markdown wrappers or description text."
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a code generation engine. Output Python code only, no markdown formatting (do not wrap in ```python ... ```)."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.1,
            timeout=45.0
        )
        
        code = response.choices[0].message.content
        if not code:
            raise Exception("Empty code generation output from OpenAI Model")
            
        return CodegenService._clean_markdown(code)

    @staticmethod
    async def _generate_anthropic(
        target_schema: dict,
        dom_tree_sample: dict,
        html_sample: str
    ) -> str:
        from anthropic import AsyncAnthropic
        
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY is not configured. Returning fallback mock extractor code.")
            return CodegenService._get_mock_extractor(target_schema)

        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        # Extract body to ignore headers, and increase snippet size to 40k chars
        from bs4 import BeautifulSoup
        import json
        try:
            soup = BeautifulSoup(html_sample, 'lxml')
            body_element = soup.body
            html_str = str(body_element)[:40000] if body_element else html_sample[:40000]
        except Exception:
            html_str = html_sample[:40000]
        dom_str = json.dumps(dom_tree_sample)[:40000]
        
        prompt = (
            f"Write a Python parsing script that extracts items matching a specified JSON schema from raw HTML.\n\n"
            f"Target Schema:\n{target_schema}\n\n"
            f"Simplified Visual DOM Tree snippet:\n{dom_str}\n\n"
            f"Raw HTML sample:\n{html_str}\n\n"
            f"Strict Constraints:\n"
            f"1. You MUST define a single asynchronous entrypoint: `async def extract(html_content: str, dom_tree: dict) -> list[dict]:`\n"
            f"2. Do NOT import or use any banned modules: 'os', 'sys', 'subprocess', 'socket', 'shutil', 'importlib', 'requests', 'httpx', 'urllib'.\n"
            f"3. You CAN import 'bs4' (BeautifulSoup), 'lxml', 'json', 're', 'datetime'.\n"
            f"4. You must NOT perform any local filesystem reads or writes (e.g. no 'open()').\n"
            f"5. The function must return a list of dictionaries matching the keys and types in the Target Schema.\n"
            f"6. Make selectors resilient by using fallback classes or tag structures where possible.\n"
            f"7. Return ONLY the raw Python code blocks, with no markdown wrappers or description text."
        )

        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2000,
            system="You are a code generation engine. Output Python code only, no markdown formatting (do not wrap in ```python ... ```).",
            messages=[
                {"role": "user", "content": prompt}
            ],
            timeout=45.0
        )
        
        code = response.content[0].text
        return CodegenService._clean_markdown(code)

    @staticmethod
    def _clean_markdown(code: str) -> str:
        code = code.strip()
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()

    @staticmethod
    def _get_mock_extractor(target_schema: dict) -> str:
        keys = list(target_schema.get("properties", {}).keys())
        if not keys:
            keys = ["title", "price"]
            
        fields_mapping = ", ".join([f"'{k}': f'Mock {k.capitalize()} Value'" for k in keys])
        
        return f"""
import re
from bs4 import BeautifulSoup

async def extract(html_content: str, dom_tree: dict) -> list[dict]:
    # Fallback parser code mapping
    soup = BeautifulSoup(html_content, 'html.parser')
    items = []
    
    # Try to find mock list nodes
    elements = soup.find_all(['div', 'li', 'tr'])
    # Return mock records matching target schema structure
    for i in range(1, 4):
        item = {{ {fields_mapping} }}
        # Try to extract numbers for fields ending in rating or price
        for k in [{", ".join([f"'{k}'" for k in keys])}]:
            if 'price' in k or 'rating' in k:
                item[k] = 10.0 * i
        items.append(item)
    return items
"""
