import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.core.exceptions import AppException
from app.core.rate_limiter import RateLimiter
from app.services.cache_service import CacheService
from app.services.email_service import get_email_service
from app.services.redis_service import RedisService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: setup and teardown."""
    logger.info("Starting SRP API...")
    app.state.email_service = get_email_service()

    # Redis-backed services
    redis_service = RedisService()
    await redis_service.connect()
    app.state.redis_service = redis_service

    app.state.rate_limiter = RateLimiter(redis_service)
    app.state.cache_service = CacheService(redis_service)

    yield

    # Shutdown
    from app.database import engine
    await engine.dispose()
    await redis_service.disconnect()
    logger.info("Shutting down SRP API...")


app = FastAPI(
    title="SRP API — Service for Regulations and Policies",
    description="Backend service for managing corporate regulations and policies",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    """Handle custom application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers or {},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """Convert Pydantic validation errors to unified format."""
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        field = None
        loc = first_error.get("loc", [])
        if len(loc) >= 2:
            field = str(loc[-1])
        message = first_error.get("msg", "Validation error")
        code = "VALIDATION_ERROR"
    else:
        field = None
        message = "Validation error"
        code = "VALIDATION_ERROR"

    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": code,
                "message": message,
                "field": field,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred",
                "field": None,
            }
        },
    )


# Include routers
app.include_router(v1_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}
