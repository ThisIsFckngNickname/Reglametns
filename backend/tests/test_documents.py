"""
Tests for document upload, parsing, CRUD, and related endpoints.
"""

import os

import pytest
from httpx import AsyncClient

from app.models.document import Document
from app.models.document_status import DocumentStatus
from app.models.document_version import DocumentVersion
from app.models.document_section import DocumentSection
from app.models.document_table import DocumentTable
from app.models.document_term import DocumentTerm
from app.models.document_abbreviation import DocumentAbbreviation
from app.models.user import User

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


def _get_sample_path(filename: str) -> str:
    """Get absolute path to a test sample file."""
    path = os.path.join(TEST_DATA_DIR, filename)
    assert os.path.exists(path), f"Test file not found: {path}"
    return path


# ─── Upload Tests ──────────────────────────────────────────────────────

class TestUploadDocument:
    """Tests for POST /api/v1/documents/upload."""

    @pytest.mark.asyncio
    async def test_upload_docx_success(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Upload a .docx file successfully and verify parsing."""
        docx_path = _get_sample_path("sample.docx")

        with open(docx_path, "rb") as f:
            response = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Test Docx Document", "description": "A test document"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["title"] == "Test Docx Document"
        assert data["status"] == DocumentStatus.DRAFT
        assert data["file_type"] == "docx"
        assert data["file_size"] > 0
        assert data["sections_count"] > 0
        assert data["terms_count"] > 0
        assert data["abbreviations_count"] > 0
        assert "id" in data

    @pytest.mark.asyncio
    async def test_upload_pdf_success(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Upload a PDF file successfully."""
        pdf_path = _get_sample_path("sample.pdf")

        with open(pdf_path, "rb") as f:
            response = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"title": "Test PDF Document"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 201, f"Response: {response.text}"
        data = response.json()
        assert data["title"] == "Test PDF Document"
        assert data["file_type"] == "pdf"
        assert data["file_size"] > 0
        assert "id" in data

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Upload a .txt file should return 400."""
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"plain text content", "text/plain")},
            data={"title": "Invalid file"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["code"] == "INVALID_FILE_TYPE"

    @pytest.mark.asyncio
    async def test_upload_too_large(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Upload a file larger than max size should return 413."""
        # 21 MB of data
        large_content = b"x" * (21 * 1024 * 1024)
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("large.docx", large_content, "application/octet-stream")},
            data={"title": "Large file"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 413
        data = response.json()
        assert data["detail"]["code"] == "FILE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_upload_no_active_company(
        self, client: AsyncClient, regular_user: User, user_token: str
    ):
        """User without active_company_id should get 403."""
        # regular_user has no active_company_id set
        docx_path = _get_sample_path("sample.docx")

        with open(docx_path, "rb") as f:
            response = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "No company"},
                headers={"Authorization": f"Bearer {user_token}"},
            )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["code"] == "NO_ACTIVE_COMPANY"

    @pytest.mark.asyncio
    async def test_upload_unauthorized(self, client: AsyncClient):
        """Without auth token, upload should return 401."""
        response = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.docx", b"content", "application/octet-stream")},
            data={"title": "No auth"},
        )
        assert response.status_code == 401


# ─── List Documents Tests ──────────────────────────────────────────────

class TestListDocuments:
    """Tests for GET /api/v1/documents."""

    @pytest.mark.asyncio
    async def test_list_documents_success(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should return paginated list of documents."""
        # Upload a document first
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "List Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        response = await client.get(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["pages"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["title"] is not None

    @pytest.mark.asyncio
    async def test_list_documents_with_status_filter(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should filter documents by status."""
        response = await client.get(
            "/api/v1/documents?status=draft",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status"] == DocumentStatus.DRAFT

    @pytest.mark.asyncio
    async def test_list_documents_with_search(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should filter documents by search query."""
        # Upload a document so there is something to search for
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Search Test Document"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        response = await client.get(
            "/api/v1/documents?search=Search+Test",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1


# ─── Get Document Detail ───────────────────────────────────────────────

class TestGetDocument:
    """Tests for GET /api/v1/documents/{id}."""

    @pytest.mark.asyncio
    async def test_get_document_success(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should return full document metadata."""
        # Upload a document first
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Detail Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc_id
        assert data["title"] == "Detail Test"
        assert data["stats"]["versions_count"] >= 1
        assert data["stats"]["sections_count"] >= 0
        assert data["status"] == DocumentStatus.DRAFT
        assert "company_id" in data

    @pytest.mark.asyncio
    async def test_get_document_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """Should return 404 for non-existent document."""
        response = await client.get(
            "/api/v1/documents/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ─── Update Document ───────────────────────────────────────────────────

class TestUpdateDocument:
    """Tests for PUT /api/v1/documents/{id}."""

    @pytest.mark.asyncio
    async def test_update_document_status(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should update document status."""
        # Upload
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Status Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Update status to review
        response = await client.put(
            f"/api/v1/documents/{doc_id}",
            json={"status": DocumentStatus.REVIEW},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == DocumentStatus.REVIEW

        # Update title
        response = await client.put(
            f"/api/v1/documents/{doc_id}",
            json={"title": "Updated Title"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_document_invalid_status(
        self, client: AsyncClient, admin_token: str, test_session
    ):
        """Should return 422 for invalid status."""
        from app.models.document import Document
        from app.models.user import User
        from sqlalchemy import select

        user = (await test_session.execute(select(User).where(User.email == "admin@test.ru"))).scalar_one()
        doc = Document(company_id=user.active_company_id, title="Invalid Status Test", created_by=user.id)
        test_session.add(doc)
        await test_session.flush()

        response = await client.put(
            f"/api/v1/documents/{doc.id}",
            json={"status": "nonexistent"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422


# ─── Archive Document ──────────────────────────────────────────────────

class TestArchiveDocument:
    """Tests for DELETE /api/v1/documents/{id}."""

    @pytest.mark.asyncio
    async def test_archive_document_success(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should archive a document."""
        # Upload
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Archive Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Archive
        response = await client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        # Verify status changed
        get_resp = await client.get(
            f"/api/v1/documents/{doc_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.json()["status"] == DocumentStatus.ARCHIVED

    @pytest.mark.asyncio
    async def test_archive_document_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """Should return 404 for non-existent document."""
        response = await client.delete(
            "/api/v1/documents/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ─── Versions ──────────────────────────────────────────────────────────

class TestDocumentVersions:
    """Tests for version-related endpoints."""

    @pytest.mark.asyncio
    async def test_get_versions(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should return list of versions."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Versions Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/versions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["version_number"] >= 1
        assert data[0]["file_type"] == "docx"

    @pytest.mark.asyncio
    async def test_download_version(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should download a specific version file."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Download Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        # Get versions to find version_id
        versions_resp = await client.get(
            f"/api/v1/documents/{doc_id}/versions",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        version_id = versions_resp.json()[0]["id"]

        # Download
        response = await client.get(
            f"/api/v1/documents/versions/{version_id}/download",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type") is not None
        assert "Content-Disposition" in response.headers

    @pytest.mark.asyncio
    async def test_download_version_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """Should return 404 for non-existent version."""
        response = await client.get(
            "/api/v1/documents/versions/99999/download",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ─── Sections ──────────────────────────────────────────────────────────

class TestDocumentSections:
    """Tests for section-related endpoints."""

    @pytest.mark.asyncio
    async def test_get_sections_tree(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should return sections as a tree."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Sections Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/sections",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

        # Check tree structure has children
        has_children = any(len(s.get("children", [])) > 0 for s in data)
        assert has_children, "Expected at least one section with children"


# ─── Terms ─────────────────────────────────────────────────────────────

class TestDocumentTerms:
    """Tests for terms endpoints."""

    @pytest.mark.asyncio
    async def test_get_terms(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should return extracted terms."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Terms Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/terms",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        # The sample docx has terms section
        assert len(data) > 0
        assert "term" in data[0]
        assert "definition" in data[0]


# ─── Abbreviations ─────────────────────────────────────────────────────

class TestDocumentAbbreviations:
    """Tests for abbreviations endpoints."""

    @pytest.mark.asyncio
    async def test_get_abbreviations(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should return extracted abbreviations."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Abbr Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/abbreviations",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        # The sample docx has abbreviations section
        assert len(data) > 0
        assert "abbreviation" in data[0]
        assert "full_form" in data[0]


# ─── Tables ────────────────────────────────────────────────────────────

class TestDocumentTables:
    """Tests for tables endpoints."""

    @pytest.mark.asyncio
    async def test_get_tables(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Should return extracted tables."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "Tables Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        doc_id = upload_resp.json()["id"]

        response = await client.get(
            f"/api/v1/documents/{doc_id}/tables",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        # The sample docx has one table
        assert len(data) >= 1
        assert "html_content" in data[0]
        assert data[0]["rows_count"] >= 1
        assert data[0]["cols_count"] >= 1


# ─── Parser Unit Tests ─────────────────────────────────────────────────

class TestDocxParser:
    """Unit tests for the DOCX parser."""

    @pytest.mark.asyncio
    async def test_parse_sample_docx(self):
        """Parse sample.docx and verify extracted data."""
        from app.services.parser_service import DocxParser

        docx_path = _get_sample_path("sample.docx")
        parser = DocxParser()
        result = parser.parse(docx_path)

        # Check sections
        assert len(result.sections) > 0
        headings = [s["title"] for s in result.sections]
        assert "Тестовый документ" in headings
        assert "Общие положения" in headings
        assert "Термины и определения" in headings

        # Check hierarchy
        top_level = [s for s in result.sections if s["parent_id"] is None]
        assert len(top_level) > 0

        # Check terms
        assert len(result.terms) > 0
        term_titles = [t["term"] for t in result.terms]
        assert any("Регламент" in t for t in term_titles)

        # Check abbreviations
        assert len(result.abbreviations) > 0
        abbr_list = [a["abbreviation"] for a in result.abbreviations]
        assert any("ООО" in a for a in abbr_list)

        # Check tables
        assert len(result.tables) > 0
        assert result.tables[0]["rows_count"] >= 3
        assert result.tables[0]["cols_count"] >= 2
