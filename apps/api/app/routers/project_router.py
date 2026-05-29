import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.project_schema import (
    ProjectCreate, ProjectResponse,
    CrawlRequest, CrawlResponse,
    SchemaProposalResponse, SchemaConfirmRequest,
    ExtractorResponse, ApiEndpointResponse,
    ApiKeyCreate, ApiKeyRevealResponse, ApiKeyResponse
)
from app.repositories.project_repo import (
    ProjectRepository, SourceRepository, SchemaRepository,
    ExtractorRepository, ApiEndpointRepository, ApiKeyRepository, UserRepository
)
from app.services.crawler_service import CrawlerService
from app.services.ai_analysis_service import AIAnalysisService
from app.services.codegen_service import CodegenService
from app.services.sandbox_service import SandboxService
from app.core.security import generate_api_key

PLAN_LIMITS = {
    "free": {"apis": 3, "requests": 100, "crawls": 20},
    "pro": {"apis": 25, "requests": 50000, "crawls": 1000},
    "startup": {"apis": 100, "requests": 500000, "crawls": 10000}
}

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])

from app.routers.auth_router import get_current_user_id_dependency as get_current_user_id


@router.post("", response_model=ProjectResponse)
def create_project(
    project_in: ProjectCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    repo = ProjectRepository(db)
    project = repo.create(user_id, project_in.name)
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        status=project.status,
        target_url=None,
        path=None
    )


@router.get("", response_model=List[ProjectResponse])
def get_projects(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    repo = ProjectRepository(db)
    projects = repo.get_user_projects(user_id)
    
    response_list = []
    source_repo = SourceRepository(db)
    endpoint_repo = ApiEndpointRepository(db)
    for p in projects:
        source = source_repo.get_by_project_id(p.id)
        endpoint = endpoint_repo.get_by_project_id(p.id)
        response_list.append(ProjectResponse(
            id=p.id,
            user_id=p.user_id,
            name=p.name,
            status=p.status,
            target_url=source.url if source else None,
            path=endpoint.path if endpoint else None
        ))
    return response_list


# API Key Endpoints
@router.post("/keys", response_model=ApiKeyRevealResponse)
def create_api_key(
    key_in: ApiKeyCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    raw_key, hashed_key = generate_api_key()
    repo = ApiKeyRepository(db)
    key_obj = repo.create(user_id, raw_key, key_in.name)
    
    # Return schema incorporating the raw key once
    return ApiKeyRevealResponse(
        id=key_obj.id,
        name=key_obj.name,
        created_at=key_obj.created_at,
        raw_key=raw_key
    )


@router.get("/keys", response_model=List[ApiKeyResponse])
def get_api_keys(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    repo = ApiKeyRepository(db)
    return repo.get_user_keys(user_id)


# Step 1: Crawl the target URL
@router.post("/crawl", response_model=CrawlResponse)
async def crawl_url(payload: CrawlRequest):
    try:
        result = await CrawlerService.crawl(payload.url)
        return CrawlResponse(
            title=result["title"],
            final_url=result["final_url"],
            html_length=len(result["html"]),
            screenshot_preview_b64=result["screenshot_b64"],
            dom_tree=result["dom_tree"]
        )
    except Exception as e:
        logger.error(f"Crawl stage failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Crawling failed: {str(e)}"
        )


# Step 2: Vision Analysis of page structure
@router.post("/analyze-visuals", response_model=SchemaProposalResponse)
async def analyze_visuals(payload: Dict[str, Any]):
    title = payload.get("title", "")
    dom_tree = payload.get("dom_tree", {})
    screenshot_b64 = payload.get("screenshot_b64", "")
    
    if not screenshot_b64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing screenshot preview data"
        )
        
    try:
        analysis = await AIAnalysisService.analyze_page(title, dom_tree, screenshot_b64)
        return analysis
    except Exception as e:
        import traceback
        logger.error(f"AI Schema analysis failure: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI structure mapping failed: {repr(e)}"
        )


# Step 3: Validate, Generate Extractor & Deploy Endpoint
@router.post("/{project_id}/deploy", response_model=ApiEndpointResponse)
async def deploy_extractor(
    project_id: str,
    confirm_in: SchemaConfirmRequest,
    db: Session = Depends(get_db)
):
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Enforce plan API quotas
    from app.models.entities import ApiEndpoint, Project as DbProject
    endpoint_repo = ApiEndpointRepository(db)
    existing_endpoint = endpoint_repo.get_by_project_id(project_id)
    if not existing_endpoint:
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(project.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_plan = (user.plan or "free").lower()
        max_apis = PLAN_LIMITS.get(user_plan, PLAN_LIMITS["free"])["apis"]
        
        # Count current active endpoints
        active_endpoints = db.query(ApiEndpoint).join(DbProject).filter(
            DbProject.user_id == user.id,
            DbProject.status == "active"
        ).count()
        
        if active_endpoints >= max_apis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Active API limit reached ({active_endpoints}/{max_apis}) for the {user_plan.upper()} plan. Please upgrade your workspace subscription."
            )

    # Fetch/Create the Source record
    source_repo = SourceRepository(db)
    source = source_repo.get_by_project_id(project_id)
    # Target URL is parsed from schema payload metadata
    metadata = confirm_in.json_schema.get("metadata", {})
    target_url = metadata.get("target_url", "")
    if not target_url:
        raise HTTPException(status_code=400, detail="Missing target_url inside schema metadata")
        
    url_template = metadata.get("url_template", None)
    proxy_enabled = metadata.get("proxy_enabled", False)
    proxy_country = metadata.get("proxy_country", None)

    if not source:
        # In a real environment, parse domain name
        domain = target_url.split("//")[-1].split("/")[0]
        source = source_repo.create(project_id, target_url, domain)

    # Update template/proxy settings on Source
    source.url_template = url_template
    source.proxy_enabled = proxy_enabled
    source.proxy_country = proxy_country
    db.commit()
    db.refresh(source)

    # Save target Schema version
    schema_repo = SchemaRepository(db)
    schema_obj = schema_repo.create(source.id, confirm_in.json_schema)

    # Crawl target URL again or extract a cached representation to run the Sandbox Test validation
    try:
        logger.info(f"Running sandbox verification for deployment on url: {target_url}")
        
        proxy_settings = None
        if proxy_enabled and proxy_country:
            if settings.PROXY_SERVER:
                proxy_settings = {
                    "enabled": True,
                    "server": settings.PROXY_SERVER,
                    "username": settings.PROXY_USERNAME,
                    "password": settings.PROXY_PASSWORD,
                    "country": proxy_country
                }
            else:
                logger.warning("Proxy rotation enabled, but PROXY_SERVER is not configured. Falling back to local direct crawl.")
            
        crawl_data = await CrawlerService.crawl(target_url, capture_screenshot=False, proxy_settings=proxy_settings)
        
        # Codegen custom BeautifulSoup script
        code = await CodegenService.generate_extractor(
            confirm_in.json_schema,
            crawl_data["dom_tree"],
            crawl_data["html"]
        )
        
        # Test code inside Sandbox
        test_extraction = await SandboxService.execute_extractor(
            code,
            crawl_data["html"],
            crawl_data["dom_tree"]
        )
        
        logger.info("Sandbox verification test passed successfully.")
        
    except Exception as e:
        logger.error(f"Sandbox verification test failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Sandbox verification test failed: {str(e)}"
        )

    # Save generated script code
    extractor_repo = ExtractorRepository(db)
    extractor_repo.create(schema_obj.id, code)

    # Create dynamic API endpoint route mapping
    endpoint_repo = ApiEndpointRepository(db)
    target_path = f"/{confirm_in.endpoint_path.strip('/')}"
    
    # Check if this path is already registered by another project
    existing_endpoint = endpoint_repo.get_by_path(target_path)
    if existing_endpoint and existing_endpoint.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"API Endpoint path '{target_path}' is already registered by another project."
        )

    endpoint = endpoint_repo.get_by_project_id(project_id)
    if not endpoint:
        endpoint = endpoint_repo.create(project_id, target_path)
    else:
        # Update path
        endpoint.path = target_path
        db.commit()
        db.refresh(endpoint)

    # Set project status to active
    project_repo.update_status(project_id, "active")

    return endpoint


@router.get("/{project_id}/schema")
def get_project_schema(
    project_id: str,
    db: Session = Depends(get_db)
):
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source_repo = SourceRepository(db)
    source = source_repo.get_by_project_id(project_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    schema_repo = SchemaRepository(db)
    schema_obj = schema_repo.get_latest_by_source_id(source.id)
    if not schema_obj:
        raise HTTPException(status_code=404, detail="Schema not found")

    return schema_obj.json_schema


from pydantic import BaseModel
class TestCodeRequest(BaseModel):
    code: str

class UpdateCodeRequest(BaseModel):
    code: str

@router.get("/{project_id}/code")
def get_project_code(
    project_id: str,
    db: Session = Depends(get_db)
):
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source_repo = SourceRepository(db)
    source = source_repo.get_by_project_id(project_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    schema_repo = SchemaRepository(db)
    schema_record = schema_repo.get_latest_by_source_id(source.id)
    if not schema_record:
        raise HTTPException(status_code=404, detail="Schema configuration not found")

    extractor_repo = ExtractorRepository(db)
    extractor = extractor_repo.get_active_by_schema_id(schema_record.id)
    if not extractor:
        raise HTTPException(status_code=404, detail="Active extractor code not found")

    return {"code": extractor.code, "version": extractor.version}

@router.post("/{project_id}/test-code")
async def test_extractor_code(
    project_id: str,
    payload: TestCodeRequest,
    db: Session = Depends(get_db)
):
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source_repo = SourceRepository(db)
    source = source_repo.get_by_project_id(project_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        # Crawl target URL again
        crawl_data = await CrawlerService.crawl(source.url, capture_screenshot=False)
        
        # Test code inside Sandbox
        results = await SandboxService.execute_extractor(
            payload.code,
            crawl_data["html"],
            crawl_data["dom_tree"]
        )
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Sandbox execution failed: {str(e)}"
        )

@router.put("/{project_id}/code")
async def update_extractor_code(
    project_id: str,
    payload: UpdateCodeRequest,
    db: Session = Depends(get_db)
):
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    source_repo = SourceRepository(db)
    source = source_repo.get_by_project_id(project_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source config missing")

    schema_repo = SchemaRepository(db)
    schema_record = schema_repo.get_latest_by_source_id(source.id)
    if not schema_record:
        raise HTTPException(status_code=404, detail="No schema configuration found. Please deploy first.")

    # Static AST safety validation
    try:
        SandboxService.verify_ast_safety(payload.code)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"AST verification failed: {str(e)}")

    extractor_repo = ExtractorRepository(db)
    extractor = extractor_repo.create(schema_record.id, payload.code)
    
    # Invalidate Redis cache if endpoint exists
    endpoint_repo = ApiEndpointRepository(db)
    endpoint = endpoint_repo.get_by_project_id(project_id)
    if endpoint:
        try:
            import redis
            from app.core.config import settings
            r = redis.from_url(settings.REDIS_URL)
            cache_key = f"api_cache:{endpoint.id}"
            r.delete(cache_key)
        except Exception:
            pass

    return {"status": "success", "message": "Extractor code updated and deployed live", "version": extractor.version}


@router.post("/{project_id}/refresh")
def refresh_project_endpoint(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    project_repo = ProjectRepository(db)
    project = project_repo.get_by_id(project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")

    endpoint_repo = ApiEndpointRepository(db)
    endpoint = endpoint_repo.get_by_project_id(project_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail="API Endpoint not deployed for this project")

    from app.workers.celery_tasks import refresh_endpoint_cache
    refresh_endpoint_cache.delay(endpoint.id)

    return {"status": "success", "message": "Background cache refresh triggered"}


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    repo = ProjectRepository(db)
    success = repo.delete(project_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "success", "message": "Project deleted successfully"}


@router.delete("/keys/{key_id}")
def revoke_api_key(
    key_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    repo = ApiKeyRepository(db)
    success = repo.delete(key_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="API Key not found")
    return {"status": "success", "message": "API Key revoked successfully"}
