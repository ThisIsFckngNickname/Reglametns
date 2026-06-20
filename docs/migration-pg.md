# Migration from SQLite to PostgreSQL

## Development (default: SQLite)
No changes needed. SQLite is used by default.

## Production (PostgreSQL)

### 1. Start PostgreSQL
```bash
docker compose up -d db
```

### 2. Configure .env
```
DATABASE_URL=postgresql+asyncpg://srp:srp_pass@localhost:5432/srp
```

### 3. Run migrations
```bash
cd backend
alembic upgrade head
```

### 4. Load seed data
```bash
python -m app.seed
```

### 5. Start backend
```bash
uvicorn app.main:app --reload
```

## Full stack with Docker
```bash
docker compose -f docker-compose.dev.yml up -d
```
