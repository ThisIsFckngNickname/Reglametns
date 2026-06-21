"""
Tests for MCP HTTP endpoint.

Covers:
- JSON-RPC 2.0 protocol (tools/list, tools/call)
- All 7 tool handlers
- Error scenarios (parse error, tool not found, missing params)
- SSE stream endpoint
- Router registration
"""
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.document import Document
from app.models.holding import Holding
from app.models.user import User
from app.models.user_holding import UserHolding


# ─── Fixture: auth headers ─────────────────────────────────────────

@pytest.fixture
def auth_headers():
    """Get auth headers for tests (using test user)."""
    return {"Authorization": "Bearer test_token"}


# ─── Tests ─────────────────────────────────────────────────────────

class TestMCPEndpoint:
    """Test MCP JSON-RPC 2.0 endpoint."""

    @pytest.mark.asyncio
    async def test_list_tools(self, client: AsyncClient, auth_headers: dict):
        """Test listing MCP tools."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        assert "tools" in data["result"]
        tool_names = [t["name"] for t in data["result"]["tools"]]
        assert "get_holding_profile" in tool_names
        assert "search_documents" in tool_names
        assert "generate_draft" in tool_names
        assert "analyze_document" in tool_names
        assert "get_holding_patterns" in tool_names
        assert "learn_from_documents" in tool_names
        assert len(tool_names) == 7

    @pytest.mark.asyncio
    async def test_get_holding_profile(
        self, client: AsyncClient, auth_headers: dict, test_session: AsyncSession
    ):
        """Test get_holding_profile tool."""
        # First create a holding
        holding = Holding(name="Test Holding", legal_form="ООО")
        test_session.add(holding)
        await test_session.flush()
        holding_id = holding.id

        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_holding_profile",
                    "arguments": {"holding_id": holding_id},
                },
                "id": 2,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["name"] == "Test Holding"

    @pytest.mark.asyncio
    async def test_search_documents(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test search_documents tool."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "search_documents",
                    "arguments": {"query": "test"},
                },
                "id": 3,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # Should be empty result with page info
        assert "items" in data["result"]
        assert data["result"]["total"] >= 0

    @pytest.mark.asyncio
    async def test_get_document_relationships_missing_id(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test get_document_relationships without document_id."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_document_relationships",
                    "arguments": {},
                },
                "id": 10,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"].get("error") == "document_id is required"

    @pytest.mark.asyncio
    async def test_tool_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test error for unknown tool."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "nonexistent_tool",
                    "arguments": {},
                },
                "id": 4,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_parse_error(self, client: AsyncClient, auth_headers: dict):
        """Test parse error handling."""
        response = await client.post(
            "/api/v1/mcp",
            content=b"not json",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32700

    @pytest.mark.asyncio
    async def test_analyze_document_missing_id(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test analyze_document without document_id."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "analyze_document",
                    "arguments": {},
                },
                "id": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"].get("error") == "document_id is required"

    @pytest.mark.asyncio
    async def test_get_holding_patterns(
        self, client: AsyncClient, auth_headers: dict, test_session: AsyncSession
    ):
        """Test get_holding_patterns tool."""
        # Create a holding with patterns
        holding = Holding(
            name="Patterns Holding",
            legal_form="ООО",
            style_settings={
                "typical_phrases": ["Настоящий документ устанавливает"],
                "documents_analyzed": 2,
            },
        )
        test_session.add(holding)
        await test_session.flush()

        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "get_holding_patterns",
                    "arguments": {"holding_id": holding.id},
                },
                "id": 6,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["name"] == "Patterns Holding"
        assert data["result"]["analysis_count"] == 2

    @pytest.mark.asyncio
    async def test_learn_from_documents_no_params(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test learn_from_documents without params."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "learn_from_documents",
                    "arguments": {},
                },
                "id": 7,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # Should error because no holding_id or document_ids provided
        assert "error" in data["result"]

    @pytest.mark.asyncio
    async def test_method_not_found(self, client: AsyncClient, auth_headers: dict):
        """Test unknown method."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "unknown_method",
                "params": {},
                "id": 8,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_get_tools_get(self, client: AsyncClient, auth_headers: dict):
        """Test GET /api/v1/mcp/tools."""
        response = await client.get("/api/v1/mcp/tools", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) == 7

    @pytest.mark.asyncio
    async def test_sse_stream(self, client: AsyncClient, auth_headers: dict):
        """Test SSE stream endpoint."""
        response = await client.get("/api/v1/mcp/stream", headers=auth_headers)
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")


class TestMCPRouterRegistration:
    """Test MCP router is registered in the FastAPI app."""

    @pytest.mark.asyncio
    async def test_mcp_routes_registered(self, client: AsyncClient):
        """Check that the MCP routes exist and respond."""
        # POST /api/v1/mcp should respond (even if parse error for empty body)
        resp = await client.post("/api/v1/mcp", content=b"{}")
        assert resp.status_code == 200
        data = resp.json()
        # Empty body still works (no id, no method) -> method not found error
        assert "error" in data

        # GET /api/v1/mcp/tools should list tools
        resp = await client.get("/api/v1/mcp/tools")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data

        # GET /api/v1/mcp/stream should return SSE
        resp = await client.get("/api/v1/mcp/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


class TestMCPGenerateDraft:
    """Tests for generate_draft tool."""

    @pytest.mark.asyncio
    async def test_generate_draft_missing_context(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test generate_draft without context."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "generate_draft",
                    "arguments": {},
                },
                "id": 20,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"].get("error") == "context is required"

    @pytest.mark.asyncio
    async def test_generate_draft_no_holding(
        self, client: AsyncClient, auth_headers: dict, test_session: AsyncSession
    ):
        """Test generate_draft without any holding in DB."""
        # No holding exists
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "generate_draft",
                    "arguments": {"context": "Test document context"},
                },
                "id": 21,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # Should error because no holding or user exists
        assert "error" in data["result"]


class TestMCPAnalyzeDocument:
    """Tests for analyze_document tool."""

    @pytest.mark.asyncio
    async def test_analyze_document_not_found(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Test analyze_document with non-existent document."""
        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "analyze_document",
                    "arguments": {"document_id": 99999},
                },
                "id": 30,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # Pattern analysis returns error for not found
        assert "error" in data["result"]


class TestMCPLearnFromDocuments:
    """Tests for learn_from_documents tool."""

    @pytest.mark.asyncio
    async def test_learn_from_documents_empty(
        self, client: AsyncClient, auth_headers: dict, test_session: AsyncSession
    ):
        """Test learn_from_documents with valid holding but no unanalyzed docs."""
        holding = Holding(name="Learn Holding", legal_form="ООО")
        test_session.add(holding)
        await test_session.flush()

        response = await client.post(
            "/api/v1/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "learn_from_documents",
                    "arguments": {"holding_id": holding.id},
                },
                "id": 40,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # No documents to analyze
        assert data["result"]["analyzed"] == 0
