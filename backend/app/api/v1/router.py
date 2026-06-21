from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.holdings import router as holdings_router
from app.api.v1.users import router as user_router
from app.api.v1.documents import router as documents_router
from app.api.v1.generator import router as generator_router
from app.api.v1.links import router as links_router
from app.api.v1.orders import router as orders_router
from app.api.v1.legislation import router as legislation_router
from app.api.v1.impact import router as impact_router
from app.api.v1.mcp import router as mcp_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(holdings_router)
router.include_router(user_router)
router.include_router(documents_router)
router.include_router(generator_router)
router.include_router(links_router)
router.include_router(orders_router)
router.include_router(legislation_router)
router.include_router(impact_router)
router.include_router(mcp_router)
