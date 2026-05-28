from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict

class WebhookConfigCreate(BaseModel):
    url: str = Field(..., description="Target webhook URL to send POST notifications")
    trigger_type: str = Field("on_change", description="Trigger type: 'on_change', 'on_new_item', 'on_failure'")
    is_active: bool = Field(True, description="Whether the webhook is active")

class WebhookConfigResponse(BaseModel):
    id: str
    project_id: str
    url: str
    trigger_type: str
    is_active: bool
    created_at: Any

    model_config = ConfigDict(from_attributes=True)

class IntegrationConfigCreate(BaseModel):
    google_sheet_url: str = Field(..., description="Google Sheet URL to write to")
    google_sheet_sync_enabled: bool = Field(True, description="Whether sync is enabled")

class IntegrationConfigResponse(BaseModel):
    id: str
    project_id: str
    google_sheet_url: Optional[str]
    google_sheet_sync_enabled: bool
    created_at: Any

    model_config = ConfigDict(from_attributes=True)
