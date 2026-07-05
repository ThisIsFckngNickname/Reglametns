"""
Pydantic схемы для multi-stage генерации.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class GenerationStatusResponse(BaseModel):
    id: str
    topic: str
    status: str
    current_stage: str
    stage_progress: int
    total_sections: int
    completed_sections: int
    provider_used: str
    document_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None


class GenerationStartResponse(BaseModel):
    generation_id: str
    status: str = "accepted"
    message: str = "Generation started. Use GET /api/generate/{id}/status to track progress."
