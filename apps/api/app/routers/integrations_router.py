import logging
import csv
import io
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
import redis.asyncio as aioredis

from app.db.session import get_db
from app.core.config import settings
from app.routers.auth_router import get_current_user_id_dependency as get_current_user_id
from app.routers import runtime_router
from app.repositories.project_repo import ProjectRepository, ApiEndpointRepository, SourceRepository, SchemaRepository, ExtractorRepository
from app.models.entities import WebhookConfig, IntegrationConfig
from app.schemas.integrations_schema import (
    WebhookConfigCreate, WebhookConfigResponse,
    IntegrationConfigCreate, IntegrationConfigResponse
)
from app.services.crawler_service import CrawlerService
from app.services.sandbox_service import SandboxService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["integrations"])

# Helper to verify project ownership
def get_verified_project(project_id: str, user_id: str, db: Session):
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    return project

# Webhook Endpoints
@router.get("/{project_id}/webhooks", response_model=List[WebhookConfigResponse])
def list_webhooks(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    get_verified_project(project_id, user_id, db)
    webhooks = db.query(WebhookConfig).filter(WebhookConfig.project_id == project_id).all()
    return webhooks

@router.post("/{project_id}/webhooks", response_model=WebhookConfigResponse)
def create_webhook(
    project_id: str,
    webhook_in: WebhookConfigCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    get_verified_project(project_id, user_id, db)
    webhook = WebhookConfig(
        project_id=project_id,
        url=webhook_in.url,
        trigger_type=webhook_in.trigger_type,
        is_active=webhook_in.is_active
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook

@router.put("/{project_id}/webhooks/{webhook_id}", response_model=WebhookConfigResponse)
def update_webhook(
    project_id: str,
    webhook_id: str,
    webhook_in: WebhookConfigCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    get_verified_project(project_id, user_id, db)
    webhook = db.query(WebhookConfig).filter(
        WebhookConfig.id == webhook_id,
        WebhookConfig.project_id == project_id
    ).first()
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook config not found"
        )
    webhook.url = webhook_in.url
    webhook.trigger_type = webhook_in.trigger_type
    webhook.is_active = webhook_in.is_active
    db.commit()
    db.refresh(webhook)
    return webhook

@router.delete("/{project_id}/webhooks/{webhook_id}")
def delete_webhook(
    project_id: str,
    webhook_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    get_verified_project(project_id, user_id, db)
    webhook = db.query(WebhookConfig).filter(
        WebhookConfig.id == webhook_id,
        WebhookConfig.project_id == project_id
    ).first()
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook config not found"
        )
    db.delete(webhook)
    db.commit()
    return {"status": "success", "message": "Webhook deleted"}

# Google Sheets Integration Endpoints
@router.get("/{project_id}/integrations/google-sheets", response_model=Optional[IntegrationConfigResponse])
def get_google_sheets_config(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    get_verified_project(project_id, user_id, db)
    config = db.query(IntegrationConfig).filter(IntegrationConfig.project_id == project_id).first()
    return config

@router.post("/{project_id}/integrations/google-sheets", response_model=IntegrationConfigResponse)
def save_google_sheets_config(
    project_id: str,
    config_in: IntegrationConfigCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    get_verified_project(project_id, user_id, db)
    config = db.query(IntegrationConfig).filter(IntegrationConfig.project_id == project_id).first()
    if not config:
        config = IntegrationConfig(
            project_id=project_id,
            google_sheet_url=config_in.google_sheet_url,
            google_sheet_sync_enabled=config_in.google_sheet_sync_enabled
        )
        db.add(config)
    else:
        config.google_sheet_url = config_in.google_sheet_url
        config.google_sheet_sync_enabled = config_in.google_sheet_sync_enabled
    db.commit()
    db.refresh(config)
    return config

# Export Data Endpoint
@router.get("/{project_id}/export/csv")
async def export_project_data_csv(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(runtime_router.get_redis_client)
):
    # Verify project
    project = get_verified_project(project_id, user_id, db)
    
    endpoint_repo = ApiEndpointRepository(db)
    endpoint = endpoint_repo.get_by_project_id(project_id)
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No API endpoint defined for this project. Cannot export data."
        )

    # Fetch cached data from Redis first
    cached_payload = None
    if redis_client:
        try:
            # Try default query hash first
            cache_key = f"api_cache:{endpoint.id}:default"
            data_str = await redis_client.get(cache_key)
            if not data_str:
                # Try key without query hash if any exists, or scan
                # We can scan keys matching "api_cache:{endpoint.id}:*"
                keys = await redis_client.keys(f"api_cache:{endpoint.id}:*")
                if keys:
                    data_str = await redis_client.get(keys[0])
            if data_str:
                cached_payload = json.loads(data_str)
        except Exception as e:
            logger.error(f"Error checking cache for export: {str(e)}")

    output_payload = cached_payload

    # If no cache, perform a live crawl & extract
    if not output_payload:
        logger.info(f"No cache found for export. Performing live crawl for project {project_id}")
        source_repo = SourceRepository(db)
        source = source_repo.get_by_project_id(project_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source page config missing for this project"
            )

        schema_repo = SchemaRepository(db)
        schema_record = schema_repo.get_latest_by_source_id(source.id)
        if not schema_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schema configuration missing"
            )

        extractor_repo = ExtractorRepository(db)
        extractor = extractor_repo.get_active_by_schema_id(schema_record.id)
        if not extractor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active extractor missing"
            )

        try:
            # Crawl
            crawl_data = await CrawlerService.crawl(source.url, capture_screenshot=False)
            extracted_items = await SandboxService.execute_extractor(
                extractor.code,
                crawl_data["html"],
                crawl_data["dom_tree"]
            )
            output_payload = {"data": extracted_items}
        except Exception as e:
            logger.error(f"Failed to crawl and extract live data: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch live data for export: {str(e)}"
            )

    items = output_payload.get("data", [])
    if not isinstance(items, list):
        if isinstance(items, dict):
            items = [items]
        else:
            items = []

    # Generate CSV content
    output = io.StringIO()
    if items:
        # Determine all unique keys across all records
        headers = []
        for item in items:
            if isinstance(item, dict):
                for k in item.keys():
                    if k not in headers:
                        headers.append(k)
            else:
                # If item is not a dict, wrap under a generic value header
                if "value" not in headers:
                    headers.append("value")

        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        
        for item in items:
            row = {}
            if isinstance(item, dict):
                for h in headers:
                    val = item.get(h, "")
                    if isinstance(val, (dict, list)):
                        row[h] = json.dumps(val)
                    else:
                        row[h] = val
            else:
                row["value"] = str(item)
            writer.writerow(row)

    csv_data = output.getvalue()
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=project_{project_id}_export.csv",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
