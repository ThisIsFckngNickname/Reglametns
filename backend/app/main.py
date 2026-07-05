"""
FastAPI приложение SRP (Service for Regulations and Policies).

Stage 2: Все провайдеры + auto-select + fallback
"""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api.routes import router
from app.api.company_profile_routes import router as company_profile_router
from app.models.session import GenerationSession
from app.models.plan import GenerationPlan
from app.models.section import DocumentSection
from app.providers.groq import GroqProvider
from app.providers.ollama import OllamaProvider
from app.providers.yandexgpt import YandexGPTProvider
from app.providers.selector import ProviderSelector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SRP Backend (Stage 2)")

    os.makedirs("generated", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    logger.info("Directories created: generated/, data/")

    init_db()
    logger.info("Database initialized")

    # Инициализация провайдеров и селектора
    groq = GroqProvider()
    ollama = OllamaProvider()
    yandexgpt = YandexGPTProvider()

    selector = ProviderSelector([groq, ollama, yandexgpt])
    app.state.selector = selector

    # Фоновый health-check
    await selector.refresh_health()
    logger.info("Providers initialized and health-checked")

    yield

    logger.info("Shutting down SRP Backend")


app = FastAPI(
    title="SRP — Service for Regulations and Policies",
    description="API для генерации корпоративных регламентов в формате .docx через AI",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(company_profile_router)


@app.get("/", tags=["health"])
async def root():
    return {"service": "SRP Backend", "version": "0.2.0", "status": "running"}
