---
name: api-tester
description: Test FastAPI endpoints with HTTPX/Pytest. Validate request/response schemas, error handling, and edge cases.
compatibility: opencode
metadata:
  audience: be, qa
  workflow: testing
---

# API Testing

## Stack
- pytest + httpx (async)
- pytest-asyncio for async tests
- TestClient from FastAPI for sync tests

## Test structure
```
tests/
├── conftest.py          # fixtures (DB, client, auth)
├── test_api/
│   ├── test_generate.py
│   ├── test_profiles.py
│   └── test_documents.py
└── test_services/
    ├── test_planner.py
    ├── test_auditor.py
    └── test_paragraph_analyzer.py
```

## What to test
- HTTP 200/201 for success
- HTTP 400/404/422 for errors
- Response body matches Pydantic schema
- Edge cases: empty input, very long input, missing fields
- Pipeline: each stage output is valid input for next

## Fixture pattern
```python
@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_generate_success(async_client):
    response = await async_client.post("/api/generate", json={...})
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
```
