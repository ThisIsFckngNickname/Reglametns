from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.users import router as user_router
from app.api.v1.documents import router as documents_router
from app.api.v1.generator import router as generator_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.company_terms import router as company_terms_router
from app.api.v1.revisions import router as revisions_router
from app.api.v1.versions import router as versions_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(companies_router)
router.include_router(user_router)
router.include_router(documents_router)
router.include_router(generator_router)
router.include_router(analysis_router)
router.include_router(company_terms_router)
router.include_router(revisions_router)
router.include_router(versions_router)
