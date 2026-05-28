import logging
import json
import hashlib
import time
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Header, HTTPException, status, Response, Request
from sqlalchemy.orm import Session
import redis.asyncio as aioredis
from app.db.session import get_db
from app.core.config import settings
from app.core.security import hash_api_key
from app.repositories.project_repo import (
    ApiEndpointRepository, ProjectRepository, SourceRepository,
    SchemaRepository, ExtractorRepository, ApiKeyRepository
)
from app.services.crawler_service import CrawlerService
from app.services.sandbox_service import SandboxService
from app.models.entities import RequestLog

logger = logging.getLogger(__name__)

PLAN_LIMITS = {
    "free": {"apis": 3, "requests": 100, "crawls": 20},
    "pro": {"apis": 25, "requests": 50000, "crawls": 1000},
    "startup": {"apis": 100, "requests": 500000, "crawls": 10000}
}

# Note: We mount this on "/apis" in main.py
router = APIRouter(prefix="/apis", tags=["runtime"])

async def get_redis_client() -> Any:
    """
    Returns an async Redis client context.
    """
    logger.info("[DEBUG get_redis_client] Resolving Redis client dependency...")
    client = None
    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        # Attempt to ping to verify connection, if it fails, catch and set to None
        await client.ping()
        logger.info("[DEBUG get_redis_client] Redis ping succeeded.")
    except Exception as e:
        logger.error(f"[DEBUG get_redis_client] Redis connection failed: {str(e)}")
        client = None

    try:
        logger.info(f"[DEBUG get_redis_client] Yielding client: {client is not None}")
        yield client
    finally:
        logger.info("[DEBUG get_redis_client] Cleaning up Redis client...")
        if client is not None:
            await client.aclose()
        logger.info("[DEBUG get_redis_client] Cleanup complete.")


def authenticate_client(
    db: Session = Depends(get_db),
    x_api_key: str = Header(..., alias=settings.API_KEY_HEADER)
) -> str:
    """
    Authenticates requests using the X-API-KEY header.
    """
    logger.info("[DEBUG authenticate_client] Authenticating key...")
    hashed_key = hash_api_key(x_api_key)
    key_repo = ApiKeyRepository(db)
    key_record = key_repo.get_by_hash(hashed_key)
    logger.info(f"[DEBUG authenticate_client] Key found: {key_record is not None}")
    
    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return key_record.user_id


@router.get("/{path:path}")
async def serve_dynamic_api(
    path: str,
    response: Response,
    request: Request,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
    user_id: str = Depends(authenticate_client),
    redis_client: Any = Depends(get_redis_client)
):
    """
    Serves generated REST API data dynamically.
    Checks Redis caching before parsing target HTML content.
    """
    start_time = time.perf_counter()
    # Standardize route query
    clean_path = f"/{path.strip('/')}"
    logger.info(f"Serving dynamic api request for path: {clean_path}")

    # Enforce request volume quota
    from datetime import datetime, timedelta, timezone
    from app.repositories.project_repo import UserRepository
    
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user_plan = (user.plan or "free").lower()
    limits = PLAN_LIMITS.get(user_plan, PLAN_LIMITS["free"])
    
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    
    # Count requests this month
    requests_this_month = db.query(RequestLog).filter(
        RequestLog.user_id == user_id,
        RequestLog.requested_at >= thirty_days_ago
    ).count()
    
    if requests_this_month >= limits["requests"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Monthly API request volume quota exceeded ({requests_this_month}/{limits['requests']}) for the {user_plan.upper()} plan. Please upgrade your workspace subscription."
        )

    # Look up Endpoint
    logger.info("[DEBUG serve_dynamic_api] Step 1: Looking up Endpoint in DB...")
    endpoint_repo = ApiEndpointRepository(db)
    endpoint = endpoint_repo.get_by_path(clean_path)
    logger.info(f"[DEBUG serve_dynamic_api] Step 1 complete. Found endpoint: {endpoint}")
    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API Endpoint path {clean_path} not found"
        )

    # Determine unique cache key based on query parameters
    query_string = request.url.query
    query_hash = hashlib.sha256(query_string.encode('utf-8')).hexdigest()[:12] if query_string else "default"
    cache_key = f"api_cache:{endpoint.id}:{query_hash}"
    cache_status = "MISS"
    status_code = 200
    output_payload = None

    try:
        # Check Cache in Redis first
        logger.info(f"[DEBUG serve_dynamic_api] Step 2: Checking Redis cache for key: {cache_key}...")
        if redis_client and not force_refresh:
            cached_data = await redis_client.get(cache_key)
            logger.info(f"[DEBUG serve_dynamic_api] Redis query result: {cached_data is not None}")
            if cached_data:
                response.headers["X-Cache"] = "HIT"
                cache_status = "HIT"
                output_payload = json.loads(cached_data)
                return output_payload

        # If cache miss (or force_refresh), we crawl the page
        logger.info("[DEBUG serve_dynamic_api] Step 3: Fetching Source configuration...")
        source_repo = SourceRepository(db)
        source = source_repo.get_by_project_id(endpoint.project_id)
        logger.info(f"[DEBUG serve_dynamic_api] Step 3 complete. Source URL: {source.url if source else None}")
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source page config missing for this project"
            )

        # Dynamic target URL compilation if template exists
        target_url = source.url
        if source.url_template:
            try:
                params = dict(request.query_params)
                target_url = source.url_template.format(**params)
                logger.info(f"Compiled target URL from template: {target_url}")
            except KeyError as ke:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing query parameter for URL template: {str(ke)}"
                )

        # Fetch latest schema & active extractor
        logger.info("[DEBUG serve_dynamic_api] Step 4: Fetching latest Schema & active Extractor...")
        schema_repo = SchemaRepository(db)
        schema_record = schema_repo.get_latest_by_source_id(source.id)
        if not schema_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Data Schema missing for this project"
            )

        extractor_repo = ExtractorRepository(db)
        extractor = extractor_repo.get_active_by_schema_id(schema_record.id)
        logger.info(f"[DEBUG serve_dynamic_api] Step 4 complete. Found extractor: {extractor is not None}")
        if not extractor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Generated extractor code missing. Re-build the endpoint."
            )

        # Perform crawl & execution sandbox flow
        # Count crawls this month
        crawls_this_month = db.query(RequestLog).filter(
            RequestLog.user_id == user_id,
            RequestLog.cache_status != "HIT",
            RequestLog.requested_at >= thirty_days_ago
        ).count()
        
        if crawls_this_month >= limits["crawls"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Monthly Playwright crawls quota exceeded ({crawls_this_month}/{limits['crawls']}) for the {user_plan.upper()} plan. Please upgrade your workspace subscription."
            )

        # Crawl target site using Playwright
        logger.info(f"[DEBUG serve_dynamic_api] Step 5: Launching crawler for URL: {target_url}...")
        
        # Route proxy settings if enabled
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

        crawl_data = await CrawlerService.crawl(target_url, capture_screenshot=False, proxy_settings=proxy_settings)
        logger.info(f"[DEBUG serve_dynamic_api] Step 5 complete. HTML length: {len(crawl_data['html'])}")
        
        # Execute script in sandbox subprocess
        logger.info("[DEBUG serve_dynamic_api] Step 6: Executing extractor code in sandbox...")
        extracted_items = await SandboxService.execute_extractor(
            extractor.code,
            crawl_data["html"],
            crawl_data["dom_tree"]
        )
        logger.info(f"[DEBUG serve_dynamic_api] Step 6 complete. Extracted {len(extracted_items)} items.")
        
        output_payload = {
            "data": extracted_items,
            "metadata": {
                "source_url": target_url,
                "endpoint_id": endpoint.id,
                "cached": False,
                "extractor_version": extractor.version
            }
        }
        
        # Write to Cache asynchronously
        if redis_client:
            await redis_client.setex(
                cache_key,
                endpoint.cache_ttl_sec,
                json.dumps(output_payload)
            )

        response.headers["X-Cache"] = "MISS"
        cache_status = "MISS"
        return output_payload
        
    except HTTPException as he:
        status_code = he.status_code
        raise he
    except Exception as e:
        logger.error(f"Execution runtime error serving path {clean_path}: {str(e)}")
        # Check if we can fall back to a stale cache entry in case of scrape errors
        if redis_client:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                logger.warning("Scraping failed. Returning stale cache item as fallback.")
                response.headers["X-Cache"] = "FALLBACK-STALE"
                cache_status = "FALLBACK-STALE"
                status_code = 200
                output_payload = json.loads(cached_data)
                return output_payload

        status_code = status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to refresh data structure: {str(e)}"
        )
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000
        try:
            log_entry = RequestLog(
                endpoint_id=endpoint.id,
                user_id=user_id,
                status_code=status_code,
                cache_status=cache_status,
                response_time_ms=duration_ms
            )
            db.add(log_entry)
            db.commit()
        except Exception as log_err:
            logger.error(f"Failed to write request log: {str(log_err)}")

