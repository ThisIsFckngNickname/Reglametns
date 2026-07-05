---
name: python-helper
description: Python/FastAPI development patterns, SQLAlchemy models, Pydantic schemas, and Alembic migrations. Ensures consistent backend architecture.
compatibility: opencode
metadata:
  audience: be
  workflow: development
---

# Python/Backend Helper

## FastAPI Patterns
- Use dependency injection for shared resources (DB session, LLM providers)
- Keep routes thin — business logic goes in services/
- Use Pydantic v2 for request/response models
- Always define response_model on route decorators

## SQLAlchemy Patterns
- Use async session when possible: `async with db.session() as session`
- Define models with explicit `__tablename__` and `__table_args__`
- Use `mapped_column` + `Mapped[]` typing (SQLAlchemy 2.0 style)
- Add `relationship()` only where needed for queries

## Project structure
```
app/
├── api/         # routes (thin)
├── models/      # SQLAlchemy models
├── schemas/     # Pydantic schemas
├── services/    # business logic
└── providers/   # external integrations (LLM, etc.)
```

## Error handling
- Define custom HTTPException subclasses
- Use `@app.exception_handler` for global handling
- Always return structured error responses: `{"detail": "...", "code": "..."}`
