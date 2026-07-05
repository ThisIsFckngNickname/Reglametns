"""
generation_plans — план (оглавление) для multi-stage генерации.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from app.database import Base


class GenerationPlan(Base):
    __tablename__ = "generation_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("generation_sessions.id"), nullable=False)
    plan_json = Column(Text, nullable=True)  # JSON: весь план с аннотациями
    raw_response = Column(Text, nullable=True)  # Сырой ответ LLM
    created_at = Column(DateTime, default=datetime.utcnow)
