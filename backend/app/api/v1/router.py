from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.users import router as user_router
from app.api.v1.documents import router as documents_router
from app.api.v1.generator import router as generator_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(companies_router)
router.include_router(user_router)
router.include_router(documents_router)
router.include_router(generator_router)
