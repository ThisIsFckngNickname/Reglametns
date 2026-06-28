"""
Tests for Phase 6 — Document Revision.

Covers:
- POST /api/v1/documents/{id}/revise
- GET  /api/v1/documents/{id}/revisions
- GET  /api/v1/documents/{id}/revisions/{rev_id}
- GET  /api/v1/documents/{id}/revisions/{rev_id}/diff
- Validation and error cases
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.document_status import DocumentStatus
from app.models.document_version import DocumentVersion
from app.models.document_revision import DocumentRevision
from app.models.user import User
from app.services.revision_service import revision_service

OLD_TEXT = """1. Общие положения

1.1. Настоящий регламент определяет порядок работы с документами.

1.2. Требования настоящего регламента обязательны для всех сотрудников.

2. Порядок работы

2.1. Документы должны быть зарегистрированы в системе.

2.2. Срок регистрации — не более 3 рабочих дней."""

NEW_TEXT = """1. Общие положения

1.1. Настоящий регламент определяет порядок работы с документами.

1.2. Требования настоящего регламента обязательны для всех сотрудников.

2. Порядок работы

2.1. Документы должны быть зарегистрированы в системе.

2.2. Срок регистрации — не более 5 рабочих дней."""

UNCHANGED_TEXT = OLD_TEXT  # Same text - no changes


@pytest.fixture
async def revision_doc(test_session: AsyncSession, admin_user: User) -> dict:
    """Create a document with a version that has full_text for revision tests."""
    doc = Document(
        company_id=admin_user.active_company_id,
        title="Тестовый регламент",
        document_type="regulation",
        status=DocumentStatus.APPROVED,
        created_by=admin_user.id,
    )
    test_session.add(doc)
    await test_session.flush()

    version = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        file_path=f"test/{admin_user.active_company_id}/{doc.id}/1_test.docx",
        file_type="docx",
        file_size=1024,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        full_text=OLD_TEXT,
        uploaded_by=admin_user.id,
    )
    test_session.add(version)
    await test_session.flush()

    return {"document_id": doc.id, "doc": doc, "version": version}


# ─── POST /revise ───────────────────────────────────────────────────────────


class TestReviseDocument:
    """Tests for POST /api/v1/documents/{id}/revise."""

    @pytest.mark.asyncio
    async def test_revise_success(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict
    ):
        """Successfully revise a document with a valid comment."""
        doc_id = revision_doc["document_id"]

        # Replace ollama_client in revision_service with mock
        mock_llm = AsyncMock()
        mock_llm.chat_completion = AsyncMock(return_value=NEW_TEXT)
        revision_service._llm_client = mock_llm

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/revise",
            json={"comment": "Изменить срок регистрации с 3 на 5 рабочих дней."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Response: {resp.text}"
        data = resp.json()
        assert data["document_id"] == doc_id
        assert data["changed"] is True
        assert data["revision_id"] is not None
        assert "diff" in data
        assert data["diff"]["stats"]["added"] >= 0
        assert data["diff"]["stats"]["removed"] >= 0

    @pytest.mark.asyncio
    async def test_revise_with_target_section(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict
    ):
        """Revision with target_section parameter."""
        doc_id = revision_doc["document_id"]
        mock_llm = AsyncMock()
        mock_llm.chat_completion = AsyncMock(return_value=NEW_TEXT)
        revision_service._llm_client = mock_llm

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/revise",
            json={
                "comment": "Изменить срок регистрации с 3 на 5 рабочих дней.",
                "target_section": "Раздел 2",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Response: {resp.text}"
        assert resp.json()["document_id"] == doc_id
        assert resp.json()["changed"] is True

    @pytest.mark.asyncio
    async def test_revise_short_comment(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict
    ):
        """Short comment ( < 10 chars) should be rejected."""
        doc_id = revision_doc["document_id"]
        resp = await client.post(
            f"/api/v1/documents/{doc_id}/revise",
            json={"comment": "коротко"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_revise_unauthorized(
        self, client: AsyncClient, revision_doc: dict
    ):
        """Missing token should return 401."""
        doc_id = revision_doc["document_id"]
        resp = await client.post(
            f"/api/v1/documents/{doc_id}/revise",
            json={"comment": "Изменить срок регистрации с 3 на 5 рабочих дней."},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_revise_nonexistent_document(
        self, client: AsyncClient, admin_token: str
    ):
        """Non-existent document should return 404."""
        resp = await client.post(
            "/api/v1/documents/99999/revise",
            json={"comment": "Изменить срок регистрации с 3 на 5 рабочих дней."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_revise_no_changes(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict
    ):
        """When LLM returns unchanged text, revision should not be created."""
        doc_id = revision_doc["document_id"]
        mock_llm = AsyncMock()
        mock_llm.chat_completion = AsyncMock(return_value=OLD_TEXT)
        revision_service._llm_client = mock_llm

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/revise",
            json={"comment": "Изменить срок регистрации с 3 на 5 рабочих дней."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["changed"] is False
        assert data["revision_id"] is None
        # No revision record should exist
        doc = revision_doc["doc"]
        assert len(doc.revisions) == 0

    @pytest.mark.asyncio
    async def test_revise_archived_document(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict
    ):
        """Archived documents should not be revisable."""
        doc_id = revision_doc["document_id"]
        doc = revision_doc["doc"]
        doc.status = DocumentStatus.ARCHIVED

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/revise",
            json={"comment": "Изменить срок регистрации с 3 на 5 рабочих дней."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_revise_llm_error(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict
    ):
        """When LLM fails, return 500."""
        doc_id = revision_doc["document_id"]
        mock_llm = AsyncMock()
        mock_llm.chat_completion = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        revision_service._llm_client = mock_llm

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/revise",
            json={"comment": "Изменить срок регистрации с 3 на 5 рабочих дней."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_revise_llm_empty_response(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict
    ):
        """When LLM returns empty, return 500."""
        doc_id = revision_doc["document_id"]
        mock_llm = AsyncMock()
        mock_llm.chat_completion = AsyncMock(return_value="")
        revision_service._llm_client = mock_llm

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/revise",
            json={"comment": "Изменить срок регистрации с 3 на 5 рабочих дней."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 500


# ─── GET /revisions ─────────────────────────────────────────────────────────


class TestGetRevisionHistory:
    """Tests for GET /api/v1/documents/{id}/revisions."""

    @pytest.mark.asyncio
    async def test_history_empty(
        self, client: AsyncClient, admin_token: str, revision_doc: dict
    ):
        """New document should have empty revision history."""
        doc_id = revision_doc["document_id"]
        resp = await client.get(
            f"/api/v1/documents/{doc_id}/revisions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_history_with_revisions(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict,
        test_session: AsyncSession,
    ):
        """Should return revision list after revisions are created."""
        doc_id = revision_doc["document_id"]
        doc = revision_doc["doc"]

        # Pre-create a revision directly in DB
        rev = DocumentRevision(
            document_id=doc_id,
            comment="Первая правка",
            target_section="Раздел 2",
            old_text=OLD_TEXT,
            new_text=NEW_TEXT,
            stats_json={"added": 1, "removed": 1, "changed": 1},
            created_by=admin_user.id,
        )
        test_session.add(rev)
        await test_session.flush()

        resp = await client.get(
            f"/api/v1/documents/{doc_id}/revisions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["comment"] == "Первая правка"
        assert data[0]["target_section"] == "Раздел 2"

    @pytest.mark.asyncio
    async def test_history_nonexistent_document(
        self, client: AsyncClient, admin_token: str
    ):
        """Non-existent document should return 404."""
        resp = await client.get(
            "/api/v1/documents/99999/revisions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


# ─── GET /revisions/{id} ────────────────────────────────────────────────────


class TestGetRevisionDetail:
    """Tests for GET /api/v1/documents/{id}/revisions/{rev_id}."""

    @pytest.mark.asyncio
    async def test_detail_success(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict,
        test_session: AsyncSession,
    ):
        """Should return revision detail with old/new text."""
        doc_id = revision_doc["document_id"]

        rev = DocumentRevision(
            document_id=doc_id,
            comment="Тестовая правка",
            old_text=OLD_TEXT,
            new_text=NEW_TEXT,
            stats_json={"added": 2, "removed": 1, "changed": 1},
            created_by=admin_user.id,
        )
        test_session.add(rev)
        await test_session.flush()
        rev_id = rev.id

        resp = await client.get(
            f"/api/v1/documents/{doc_id}/revisions/{rev_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Response: {resp.text}"
        data = resp.json()
        assert data["id"] == rev_id
        assert data["comment"] == "Тестовая правка"
        assert data["old_text"] == OLD_TEXT
        assert data["new_text"] == NEW_TEXT
        assert data["stats"]["added"] == 2

    @pytest.mark.asyncio
    async def test_detail_not_found(
        self, client: AsyncClient, admin_token: str, revision_doc: dict
    ):
        """Non-existent revision should return 404."""
        doc_id = revision_doc["document_id"]
        resp = await client.get(
            f"/api/v1/documents/{doc_id}/revisions/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


# ─── GET /revisions/{id}/diff ───────────────────────────────────────────────


class TestGetRevisionDiff:
    """Tests for GET /api/v1/documents/{id}/revisions/{rev_id}/diff."""

    @pytest.mark.asyncio
    async def test_diff_success(
        self, client: AsyncClient, admin_user: User, admin_token: str, revision_doc: dict,
        test_session: AsyncSession,
    ):
        """Should return diff for a revision."""
        doc_id = revision_doc["document_id"]

        rev = DocumentRevision(
            document_id=doc_id,
            comment="Тестовая правка",
            old_text=OLD_TEXT,
            new_text=NEW_TEXT,
            stats_json={"added": 1, "removed": 1, "changed": 1},
            created_by=admin_user.id,
        )
        test_session.add(rev)
        await test_session.flush()
        rev_id = rev.id

        resp = await client.get(
            f"/api/v1/documents/{doc_id}/revisions/{rev_id}/diff",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Response: {resp.text}"
        data = resp.json()
        assert data["old_text"] == OLD_TEXT
        assert data["new_text"] == NEW_TEXT
        assert "diff" in data
        assert data["diff"]["stats"]["added"] >= 0

    @pytest.mark.asyncio
    async def test_diff_revision_not_found(
        self, client: AsyncClient, admin_token: str, revision_doc: dict
    ):
        """Non-existent revision diff should return 404."""
        doc_id = revision_doc["document_id"]
        resp = await client.get(
            f"/api/v1/documents/{doc_id}/revisions/99999/diff",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


# ─── DiffService unit tests ─────────────────────────────────────────────────


class TestDiffService:
    """Unit tests for DiffService."""

    def test_generate_diff_changes(self):
        """Diff should detect changes between two texts."""
        from app.services.diff_service import diff_service
        old = "строка 1\nстрока 2\nстрока 3"
        new = "строка 1\nстрока изменена\nстрока 3"
        result = diff_service.generate_diff(old, new)
        assert result.stats.added > 0 or result.stats.removed > 0 or result.stats.changed > 0
        assert "unified_diff" in result.model_dump()
        assert "html_diff" in result.model_dump()

    def test_generate_diff_identical(self):
        """Diff of identical texts should show no changes."""
        from app.services.diff_service import diff_service
        text = "одинаковый текст"
        result = diff_service.generate_diff(text, text)
        assert result.stats.added == 0
        assert result.stats.removed == 0
        assert result.stats.changed == 0

    def test_generate_diff_empty(self):
        """Diff with empty strings should handle gracefully."""
        from app.services.diff_service import diff_service
        result = diff_service.generate_diff("", "")
        assert result.stats.added == 0
        assert result.stats.removed == 0
        assert result.stats.changed == 0

    def test_is_unchanged_true(self):
        """is_unchanged should return True for identical texts."""
        from app.services.diff_service import diff_service
        assert diff_service.is_unchanged("text", "text") is True

    def test_is_unchanged_false(self):
        """is_unchanged should return False for different texts."""
        from app.services.diff_service import diff_service
        assert diff_service.is_unchanged("old", "new") is False

    def test_is_unchanged_whitespace(self):
        """is_unchanged should ignore leading/trailing whitespace."""
        from app.services.diff_service import diff_service
        assert diff_service.is_unchanged("text", "  text  ") is True
