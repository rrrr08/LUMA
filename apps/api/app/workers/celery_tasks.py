import json
import logging
import asyncio
import time
import httpx
from typing import Any
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.repositories.project_repo import (
    ApiEndpointRepository, SourceRepository, SchemaRepository,
    ExtractorRepository, ProjectRepository
)
from app.services.crawler_service import CrawlerService
from app.services.sandbox_service import SandboxService
from app.core.config import settings
from app.models.entities import WebhookConfig, IntegrationConfig
import redis

logger = get_task_logger(__name__)

# Run helper in async loop because crawler/sandbox are async
def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@celery_app.task(
    name="app.workers.celery_tasks.dispatch_webhook_task",
    bind=True,
    max_retries=3,
    default_retry_delay=5
)
def dispatch_webhook_task(self, webhook_url: str, payload: dict) -> bool:
    """
    Sends an HTTP POST webhook request with exponential backoff on failure.
    """
    logger.info(f"Dispatching webhook event to {webhook_url}")
    try:
        with httpx.Client() as client:
            response = client.post(webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
        logger.info(f"Webhook delivered successfully to {webhook_url}")
        return True
    except Exception as exc:
        logger.warning(f"Webhook dispatch failed to {webhook_url}: {str(exc)}. Retrying...")
        retry_delay = 5 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=retry_delay)

@celery_app.task(name="app.workers.celery_tasks.refresh_endpoint_cache")
def refresh_endpoint_cache(endpoint_id: str) -> bool:
    """
    Crawls and extracts data for a single API endpoint, checks for data drift,
    dispatches webhooks on drift, and updates the Redis cache.
    """
    logger.info(f"Starting cache refresh for endpoint {endpoint_id}")
    db = SessionLocal()
    try:
        # Resolve DB entities
        from app.models.entities import ApiEndpoint
        endpoint = db.query(ApiEndpoint).filter(ApiEndpoint.id == endpoint_id).first()

        if not endpoint:
            logger.error(f"Endpoint {endpoint_id} not found in DB.")
            return False

        source_repo = SourceRepository(db)
        source = source_repo.get_by_project_id(endpoint.project_id)
        if not source:
            logger.error(f"Source config for endpoint {endpoint_id} not found.")
            return False

        schema_repo = SchemaRepository(db)
        schema_record = schema_repo.get_latest_by_source_id(source.id)
        if not schema_record:
            logger.error(f"Schema for endpoint {endpoint_id} not found.")
            return False

        extractor_repo = ExtractorRepository(db)
        extractor = extractor_repo.get_active_by_schema_id(schema_record.id)
        if not extractor:
            logger.error(f"Active extractor for endpoint {endpoint_id} not found.")
            return False

        # Build proxy settings if configured
        proxy_settings = None
        if source.proxy_enabled and source.proxy_country:
            if settings.PROXY_SERVER:
                proxy_settings = {
                    "enabled": True,
                    "server": settings.PROXY_SERVER,
                    "username": settings.PROXY_USERNAME,
                    "password": settings.PROXY_PASSWORD,
                    "country": source.proxy_country
                }
            else:
                logger.warning("Proxy rotation enabled, but PROXY_SERVER is not configured. Falling back to local direct crawl.")

        # Run async crawler and sandbox service
        async def crawl_and_extract():
            crawl_data = await CrawlerService.crawl(source.url, capture_screenshot=False, proxy_settings=proxy_settings)
            extracted_items = await SandboxService.execute_extractor(
                extractor.code,
                crawl_data["html"],
                crawl_data["dom_tree"]
            )
            return crawl_data, extracted_items

        crawl_data, extracted_items = run_async(crawl_and_extract())

        # Connect to Redis
        r = redis.from_url(settings.REDIS_URL)
        
        # We check both legacy cache key and parameter-based default key
        cache_key_default = f"api_cache:{endpoint.id}:default"
        cache_key_legacy = f"api_cache:{endpoint.id}"
        
        old_payload_str = r.get(cache_key_default) or r.get(cache_key_legacy)
        old_items = []
        if old_payload_str:
            try:
                old_payload = json.loads(old_payload_str)
                old_items = old_payload.get("data", [])
            except Exception as pe:
                logger.error(f"Failed to parse old cached payload: {str(pe)}")

        # Check for Data Drift
        has_drifted = False
        if old_payload_str is None:
            # First crawl, no previous cache
            has_drifted = False
        else:
            if old_items != extracted_items:
                has_drifted = True
                logger.info(f"Data drift detected for endpoint {endpoint_id}!")

        # Trigger Webhooks if drift detected
        if has_drifted:
            webhooks = db.query(WebhookConfig).filter(
                WebhookConfig.project_id == endpoint.project_id,
                WebhookConfig.is_active == True,
                WebhookConfig.trigger_type == "on_change"
            ).all()
            
            if webhooks:
                webhook_payload = {
                    "event": "data_drift",
                    "project_id": endpoint.project_id,
                    "endpoint_path": endpoint.path,
                    "timestamp": time.time(),
                    "data": extracted_items
                }
                for webhook in webhooks:
                    dispatch_webhook_task.delay(webhook.url, webhook_payload)
                    logger.info(f"Queued webhook dispatch task for url: {webhook.url}")

        # Trigger Google Sheets integration if enabled
        integration = db.query(IntegrationConfig).filter(
            IntegrationConfig.project_id == endpoint.project_id,
            IntegrationConfig.google_sheet_sync_enabled == True
        ).first()
        
        if integration and integration.google_sheet_url:
            logger.info(
                f"[SIMULATION] Synchronizing {len(extracted_items)} items for project {endpoint.project_id} "
                f"to Google Sheet: {integration.google_sheet_url}"
            )

        output_payload = {
            "data": extracted_items,
            "metadata": {
                "source_url": source.url,
                "endpoint_id": endpoint.id,
                "cached": False,
                "extractor_version": extractor.version
            }
        }

        # Write to both Redis keys for compatibility
        r.setex(cache_key_default, endpoint.cache_ttl_sec, json.dumps(output_payload))
        r.setex(cache_key_legacy, endpoint.cache_ttl_sec, json.dumps(output_payload))
        
        logger.info(f"Cache refreshed successfully for endpoint {endpoint_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to refresh endpoint {endpoint_id}: {str(e)}", exc_info=True)
        return False
    finally:
        db.close()


@celery_app.task(name="app.workers.celery_tasks.refresh_all_active_endpoints")
def refresh_all_active_endpoints() -> int:
    """
    Scans for all active projects, finds their endpoints, and triggers refreshes.
    """
    logger.info("Scanning active endpoints for cache refreshes...")
    db = SessionLocal()
    try:
        from app.models.entities import ApiEndpoint, Project
        active_endpoints = db.query(ApiEndpoint).join(Project).filter(
            Project.status == "active"
        ).all()
        
        triggered_count = 0
        for endpoint in active_endpoints:
            refresh_endpoint_cache.delay(endpoint.id)
            triggered_count += 1
            
        logger.info(f"Triggered cache refresh tasks for {triggered_count} endpoints.")
        return triggered_count
    except Exception as e:
        logger.error(f"Error scanning active endpoints: {str(e)}", exc_info=True)
        return 0
    finally:
        db.close()

