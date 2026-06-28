"""
Pydantic schemas for analysis pipeline API.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AnalysisStepStatus(BaseModel):
    """Status of a single pipeline step."""
    status: str  # "waiting" | "running" | "done" | "error"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class AnalysisStatusResponse(BaseModel):
    """Detailed status of an analysis pipeline run."""
    id: int
    document_id: int
    document_version_id: Optional[int] = None
    file_hash: Optional[str] = None
    status: str  # "running" | "complete" | "error"
    steps_status: dict[str, AnalysisStepStatus] = {}
    error_message: Optional[str] = None
    result_summary: Optional[dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AnalysisHistoryItem(BaseModel):
    """Summary of a single analysis run for history listing."""
    id: int
    document_id: int
    document_version_id: Optional[int] = None
    status: str  # "running" | "complete" | "error"
    error_message: Optional[str] = None
    result_summary: Optional[dict] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReanalyzeResponse(BaseModel):
    """Response after triggering a reanalysis."""
    analysis_id: int
    document_id: int
    status: str  # всегда "running"
    message: str  # "Reanalysis started"
