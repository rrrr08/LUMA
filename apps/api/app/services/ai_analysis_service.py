import json
import logging
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Define the Pydantic classes for schema validation
class FieldDefinition(BaseModel):
    name: str = Field(description="snake_case field name, e.g. price_per_night, hotel_name")
    type: str = Field(description="Data type of the field, e.g., string, number, boolean")
    description: str = Field(description="Short description of what this field extracts")
    sample_value: str = Field(description="An actual sample of the value observed on the page")
    selector_hint: str = Field(description="A CSS selector or visual structure hint (e.g. '.listing-card .price')")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")

class PaginationDefinition(BaseModel):
    exists: bool = Field(description="Whether pagination controls are found on the page")
    pagination_type: str = Field(description="Type of pagination: next_button, page_numbers, load_more, infinite_scroll, none")
    selector_hint: Optional[str] = Field(default=None, description="CSS selector for the next page button or paginator")

class SchemaAnalysis(BaseModel):
    page_type: str = Field(description="Main category of the page, e.g., product_listing, list_directory, single_details, search_results")
    primary_entity_name: str = Field(description="Singular entity name of repeating blocks, e.g., hotel, flight, job_posting, book")
    fields: List[FieldDefinition] = Field(description="List of fields parsed inside each repeating element block")
    pagination: PaginationDefinition = Field(description="Pagination mapping details")
    confidence_score: float = Field(description="Overall confidence in the page structure analysis from 0.0 to 1.0")

class AIAnalysisService:
    @classmethod
    async def analyze_page(
        cls,
        title: str,
        dom_tree: dict,
        screenshot_b64: str
    ) -> SchemaAnalysis:
        """
        Main entrypoint. Dispatches the request to the configured AI provider.
        """
        provider = settings.AI_PROVIDER.lower()
        logger.info(f"Dispatching page structure analysis to provider: {provider}")
        
        if provider == "openai":
            return await cls._analyze_openai(title, dom_tree, screenshot_b64)
        elif provider == "openai_compatible":
            return await cls._analyze_openai_compatible(title, dom_tree, screenshot_b64)
        elif provider == "anthropic":
            return await cls._analyze_anthropic(title, dom_tree, screenshot_b64)
        else:
            logger.warning(f"Unknown AI Provider '{provider}'. Falling back to Mock Schema.")
            return cls._get_mock_schema()

    @classmethod
    async def _analyze_openai(
        cls,
        title: str,
        dom_tree: dict,
        screenshot_b64: str
    ) -> SchemaAnalysis:
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not configured. Returning fallback mock schema.")
            return cls._get_mock_schema()
            
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return await cls._call_openai_client(client, settings.OPENAI_VISION_MODEL, title, dom_tree, screenshot_b64)

    @classmethod
    async def _analyze_openai_compatible(
        cls,
        title: str,
        dom_tree: dict,
        screenshot_b64: str
    ) -> SchemaAnalysis:
        # Base url override
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not configured. Returning fallback mock schema.")
            return cls._get_mock_schema()
            
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE_URL
        )
        return await cls._call_openai_client(client, settings.OPENAI_VISION_MODEL, title, dom_tree, screenshot_b64)

    @staticmethod
    async def _call_openai_client(
        client: AsyncOpenAI,
        model: str,
        title: str,
        dom_tree: dict,
        screenshot_b64: str
    ) -> SchemaAnalysis:
        dom_str = json.dumps(dom_tree)[:40000]
        prompt = (
            f"You are an expert data scraper analyst. Below is the metadata and a snapshot of a webpage.\n"
            f"Page Title: {title}\n"
            f"Simplified DOM Structure Sample: {dom_str}\n\n"
            f"Tasks:\n"
            f"1. Examine the visual layout in the screenshot and the markup structure in the DOM.\n"
            f"2. Identify repeating entity blocks (e.g. cards, list rows, grid items).\n"
            f"3. Propose a structured data schema for the main repeating entities.\n"
            f"4. Fill out the response format adhering strictly to the structured outputs layout."
        )
        
        response = await client.beta.chat.completions.parse(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{screenshot_b64}"
                            }
                        }
                    ]
                }
            ],
            response_format=SchemaAnalysis,
            max_tokens=1500,
            timeout=120.0
        )
        result = response.choices[0].message.parsed
        if not result:
            raise Exception("Failed to receive structured output from OpenAI API.")
        return result

    @staticmethod
    async def _analyze_anthropic(
        title: str,
        dom_tree: dict,
        screenshot_b64: str
    ) -> SchemaAnalysis:
        from anthropic import AsyncAnthropic
        
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY is not configured. Returning fallback mock schema.")
            return AIAnalysisService._get_mock_schema()

        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        dom_str = json.dumps(dom_tree)[:40000]
        
        prompt = (
            f"Examine this page screenshot and simplified DOM tree context.\n"
            f"Page Title: {title}\n"
            f"DOM tree: {dom_str}\n\n"
            f"Analyze the structure and record the results by calling the tool 'record_schema_analysis'."
        )

        tool_spec = {
            "name": "record_schema_analysis",
            "description": "Records the data schema and pagination analysis of a target webpage.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "page_type": {
                        "type": "string",
                        "description": "Main category of the page, e.g., product_listing, list_directory, details"
                    },
                    "primary_entity_name": {
                        "type": "string",
                        "description": "Singular entity name of repeating blocks, e.g. hotel, product, contest"
                    },
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "snake_case name"},
                                "type": {"type": "string", "description": "string, number, boolean"},
                                "description": {"type": "string"},
                                "sample_value": {"type": "string"},
                                "selector_hint": {"type": "string"},
                                "confidence": {"type": "number"}
                            },
                            "required": ["name", "type", "description", "sample_value", "selector_hint", "confidence"]
                        }
                    },
                    "pagination": {
                        "type": "object",
                        "properties": {
                            "exists": {"type": "boolean"},
                            "pagination_type": {"type": "string", "description": "next_button, page_numbers, load_more, infinite_scroll, none"},
                            "selector_hint": {"type": "string"}
                        },
                        "required": ["exists", "pagination_type"]
                    },
                    "confidence_score": {
                        "type": "number",
                        "description": "Overall confidence score"
                    }
                },
                "required": ["page_type", "primary_entity_name", "fields", "pagination", "confidence_score"]
            }
        }

        response = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1500,
            tools=[tool_spec],
            tool_choice={"type": "tool", "name": "record_schema_analysis"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            timeout=45.0
        )

        # Retrieve the tool call input arguments
        tool_use = next(block for block in response.content if block.type == "tool_use")
        input_data = tool_use.input
        return SchemaAnalysis(**input_data)

    @staticmethod
    def _get_mock_schema() -> SchemaAnalysis:
        return SchemaAnalysis(
            page_type="product_listing",
            primary_entity_name="item",
            fields=[
                FieldDefinition(
                    name="title",
                    type="string",
                    description="The main title of the listing card",
                    sample_value="Sample Product Name",
                    selector_hint=".card-title, h3",
                    confidence=0.9
                ),
                FieldDefinition(
                    name="price",
                    type="number",
                    description="The parsed price value",
                    sample_value="49.99",
                    selector_hint=".price, .amount",
                    confidence=0.85
                )
            ],
            pagination=PaginationDefinition(
                exists=False,
                pagination_type="none"
            ),
            confidence_score=0.9
        )
