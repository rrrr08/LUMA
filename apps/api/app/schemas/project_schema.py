from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# Auth & User schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    role: str
    plan: Optional[str] = "free"
    
    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Project schemas
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)

class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    status: str
    target_url: Optional[str] = None
    path: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# Crawl schemas
class CrawlRequest(BaseModel):
    url: str

class CrawlResponse(BaseModel):
    title: str
    final_url: str
    html_length: int
    screenshot_preview_b64: str
    dom_tree: Dict[str, Any]

# Schema Definition schemas
class FieldSchema(BaseModel):
    name: str
    type: str
    description: str
    sample_value: str
    selector_hint: str
    confidence: float

class SchemaProposalResponse(BaseModel):
    page_type: str
    primary_entity_name: str
    fields: List[FieldSchema]
    confidence_score: float

class SchemaConfirmRequest(BaseModel):
    json_schema: Dict[str, Any]
    endpoint_path: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")

# Deployment schemas
class ExtractorResponse(BaseModel):
    id: str
    schema_id: str
    code: str
    version: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ApiEndpointResponse(BaseModel):
    id: str
    project_id: str
    path: str
    method: str
    cache_ttl_sec: int

    model_config = ConfigDict(from_attributes=True)

# ApiKey schemas
class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    created_at: Any
    
    model_config = ConfigDict(from_attributes=True)

class ApiKeyRevealResponse(ApiKeyResponse):
    raw_key: str


class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    plan: str
    amount: float
    status: str
    billing_date: Any

    model_config = ConfigDict(from_attributes=True)


class QuotaSettingsResponse(BaseModel):
    email_alerts_enabled: bool
    slack_alerts_enabled: bool
    slack_webhook_url: Optional[str] = None
    threshold_percentage: int

    model_config = ConfigDict(from_attributes=True)


class QuotaSettingsUpdate(BaseModel):
    email_alerts_enabled: bool
    slack_alerts_enabled: bool
    slack_webhook_url: Optional[str] = None
    threshold_percentage: int = Field(80, ge=10, le=100)


class RazorpayOrderCreate(BaseModel):
    plan: str
    promo_code: Optional[str] = None


class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: Optional[str] = None
    is_mock: bool


class RazorpayPaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    plan: str
    amount_usd: float
    promo_code: Optional[str] = None


