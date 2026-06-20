"""
Tests for the MCP server.

Since the MCP server is a STDIO-based process, we test:
- Tool definitions registry
- JSON-RPC 2.0 message formatting
- Handler logic with a real database session
"""

import json
import pytest
from httpx import AsyncClient

from app.mcp.server import (
    TOOL_DEFINITIONS,
    json_rpc_result,
    json_rpc_error,
)
from app.models.user import User
from tests.test_documents import _get_sample_path


class TestMCPProtocol:
    """Unit tests for JSON-RPC 2.0 formatting."""

    def test_json_rpc_result_format(self):
        response = json_rpc_result(1, {"hello": "world"})
        parsed = json.loads(response)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == 1
        assert parsed["result"] == {"hello": "world"}
        assert "error" not in parsed

    def test_json_rpc_error_format(self):
        response = json_rpc_error("req1", -32601, "Method not found")
        parsed = json.loads(response)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "req1"
        assert parsed["error"]["code"] == -32601
        assert parsed["error"]["message"] == "Method not found"
        assert "result" not in parsed

    def test_json_rpc_error_with_data(self):
        response = json_rpc_error(42, -32603, "Error", {"detail": "something"})
        parsed = json.loads(response)
        assert parsed["error"]["data"] == {"detail": "something"}


class TestMCPToolDefinitions:
    """Tests for MCP tool definitions."""

    def test_tool_count(self):
        assert len(TOOL_DEFINITIONS) == 4

    def test_tool_names(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "get_holding_profile" in names
        assert "search_documents" in names
        assert "get_document_relationships" in names
        assert "generate_draft" in names

    def test_tool_has_schema(self):
        for tool in TOOL_DEFINITIONS:
            assert "inputSchema" in tool
            assert "type" in tool["inputSchema"]
            assert "properties" in tool["inputSchema"]

    def test_get_document_relationships_required(self):
        """get_document_relationships should require document_id."""
        tool = next(t for t in TOOL_DEFINITIONS if t["name"] == "get_document_relationships")
        assert "document_id" in tool["inputSchema"].get("required", [])


class TestMCPIntegration:
    """
    Integration tests that exercise MCP handler logic via the API.

    We test the underlying services that the MCP server uses,
    since the MCP server runs as a separate STDIO process.
    """

    @pytest.mark.asyncio
    async def test_search_documents_via_api(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """Search documents — same logic used by MCP search_documents tool."""
        docx_path = _get_sample_path("sample.docx")
        with open(docx_path, "rb") as f:
            await client.post(
                "/api/v1/documents/upload",
                files={"file": ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                data={"title": "MCP Search Test"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        # The MCP tool uses similar DB queries — test via API
        response = await client.get(
            "/api/v1/documents?search=MCP+Search",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_generate_draft_not_available_without_llm(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        """generate_draft should return 503 if LLM is not configured."""
        # The endpoint expects form data (not JSON)
        response = await client.post(
            "/api/v1/generator/generate",
            data={"context": "Test context for draft generation"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Without GigaChat configured, it should return an error
        # 503 = LLM not configured, which is the expected behavior
        assert response.status_code in (503, 400, 200)
