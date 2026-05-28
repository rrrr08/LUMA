import time
import uuid
import logging
import sys
import asyncio
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import setup_logging, correlation_id_ctx
from app.db.init_db import init_db
from app.routers import project_router, runtime_router, auth_router, analytics_router, integrations_router

# Configure logging at boot
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schemas...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Database initialization failed: {str(e)}", exc_info=True)
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Turns structured websites into live REST APIs dynamically.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Set CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID and performance telemetry middleware
@app.middleware("http")
async def add_correlation_id_and_telemetry(request: Request, call_next):
    # Retrieve existing Correlation ID header or generate a new one
    corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    correlation_id_token = correlation_id_ctx.set(corr_id)
    
    start_time = time.perf_counter()
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    
    try:
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"Completed request: {request.method} {request.url.path} - Status: {response.status_code} in {duration_ms:.2f}ms",
            extra={"extra_data": {"duration_ms": duration_ms}}
        )
        response.headers["X-Correlation-ID"] = corr_id
        return response
    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"Unhandled exception during request processing: {str(e)} in {duration_ms:.2f}ms",
            exc_info=True,
            extra={"extra_data": {"duration_ms": duration_ms}}
        )
        raise e
    finally:
        correlation_id_ctx.reset(correlation_id_token)


# Mount routes
app.include_router(auth_router.router, prefix=settings.API_V1_STR)
app.include_router(project_router.router, prefix=settings.API_V1_STR)
app.include_router(analytics_router.router, prefix=settings.API_V1_STR)
app.include_router(runtime_router.router, prefix=settings.API_V1_STR)
app.include_router(integrations_router.router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["system"])
def health_check():
    return {"status": "ok", "timestamp": time.time()}
