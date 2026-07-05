---
name: db-schema
description: Database schema design, SQLAlchemy models, migration strategy, and query optimization for the SRP project.
compatibility: opencode
metadata:
  audience: be
  workflow: development
---

# Database Schema Helper

## SQLAlchemy 2.0 style
```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey
from datetime import datetime

class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

## Migration strategy
- Use Alembic for all schema changes
- Each migration = one logical change (not bulk)
- Always test downgrade before deploy
- Never edit existing migrations after review

## Index strategy
- Index all foreign keys
- Index columns used in WHERE/ORDER BY
- Use composite indexes for multi-column queries
- Avoid over-indexing (write overhead)

## Best practices
- Use `String(36)` for UUID fields, not `Text`
- Use `Text` for long content, `String` for short (<255)
- Add `__table_args__` for constraints and indexes
- Define `repr()` for debugging
- Keep models in separate files by domain
