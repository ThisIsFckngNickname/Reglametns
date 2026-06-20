"""
MCP Server — STDIO JSON-RPC 2.0 interface.

This server runs as a separate process and communicates via stdin/stdout.
It exposes the following tools:

1. get_holding_profile   — retrieve holding configuration
2. search_documents      — search documents in the registry
3. get_document_relationships — get the relationship graph for a document
4. generate_draft        — generate a draft document from context + files

Protocol: JSON-RPC 2.0 over STDIO.
Each message is a single line of JSON terminated by '\n'.
"""

import json
import logging
import sys
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ─── JSON-RPC 2.0 Helpers ──────────────────────────────────────────

def json_rpc_error(id_: Any, code: int, message: str, data: Any = None) -> str:
    """Build a JSON-RPC 2.0 error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return json.dumps({"jsonrpc": "2.0", "error": error, "id": id_}, ensure_ascii=False)


def json_rpc_result(id_: Any, result: Any) -> str:
    """Build a JSON-RPC 2.0 success response."""
    return json.dumps({"jsonrpc": "2.0", "result": result, "id": id_}, ensure_ascii=False)


# ─── Tool Definitions ──────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_holding_profile",
        "description": "Get the holding profile (name, INN, legal form, template settings, GOST flag).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "holding_id": {
                    "type": "integer",
                    "description": "Holding ID (optional — uses default if omitted)",
                }
            },
        },
    },
    {
        "name": "search_documents",
        "description": "Search documents in the registry by title, status, or full-text query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (title/description)"},
                "status": {"type": "string", "description": "Filter by status (draft/review/approved/archived)"},
                "holding_id": {"type": "integer", "description": "Holding ID filter"},
                "page": {"type": "integer", "description": "Page number (default 1)"},
                "page_size": {"type": "integer", "description": "Items per page (default 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_document_relationships",
        "description": "Get all relationships (links, orders) for a document — the impact map.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "integer", "description": "Document ID"},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "generate_draft",
        "description": "Generate a draft document from context description. Optionally reference a holding for template.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {"type": "string", "description": "Context description of what the document should regulate"},
                "holding_id": {"type": "integer", "description": "Holding ID for template/style"},
            },
            "required": ["context"],
        },
    },
]


# ─── Tool Handlers ─────────────────────────────────────────────────

class MCPToolHandler:
    """
    Handles MCP tool execution by delegating to the appropriate backend service.
    Uses direct database access for simplicity (no FastAPI dependency).
    """

    def __init__(self):
        self._db_session_factory = None

    def set_db_session_factory(self, factory: Any) -> None:
        """Set a callable that returns an async database session."""
        self._db_session_factory = factory

    async def get_holding_profile(self, params: dict) -> dict:
        """Get holding profile by ID or default."""
        from app.models.holding import Holding
        from sqlalchemy import select

        holding_id = params.get("holding_id")
        async with self._db_session_factory() as db:
            if holding_id:
                stmt = select(Holding).where(Holding.id == holding_id)
            else:
                stmt = select(Holding).limit(1)
            result = await db.execute(stmt)
            holding = result.scalar_one_or_none()
            if holding is None:
                return {"error": "Holding not found"}
            return {
                "id": holding.id,
                "name": holding.name,
                "inn": holding.inn or "",
                "legal_form": holding.legal_form,
                "use_gost": holding.use_gost,
                "document_structure": holding.document_structure or {},
                "style_settings": holding.style_settings or {},
            }

    async def search_documents(self, params: dict) -> dict:
        """Search documents in the registry."""
        from app.models.document import Document
        from sqlalchemy import select

        query = params.get("query", "")
        status = params.get("status")
        holding_id = params.get("holding_id")
        page = params.get("page", 1)
        page_size = params.get("page_size", 20)

        async with self._db_session_factory() as db:
            stmt = select(Document)
            if query:
                stmt = stmt.where(
                    Document.title.ilike(f"%{query}%")
                    | Document.description.ilike(f"%{query}%")
                )
            if status:
                stmt = stmt.where(Document.status == status)
            if holding_id:
                stmt = stmt.where(Document.holding_id == holding_id)

            # Count
            count_stmt = stmt.with_only_columns(Document.id)
            count_result = await db.execute(count_stmt)
            total = len(count_result.scalars().all())

            # Paginate
            stmt = stmt.order_by(Document.created_at.desc())
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
            result = await db.execute(stmt)
            docs = result.scalars().all()

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [
                    {
                        "id": d.id,
                        "title": d.title,
                        "description": d.description or "",
                        "status": d.status,
                        "holding_id": d.holding_id,
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                    }
                    for d in docs
                ],
            }

    async def get_document_relationships(self, params: dict) -> dict:
        """Get the impact map for a document."""
        from app.models.document import Document
        from app.models.document_link import DocumentLink
        from app.models.order import Order
        from app.models.order_document_link import OrderDocumentLink
        from sqlalchemy import select

        document_id = params.get("document_id")
        if not document_id:
            return {"error": "document_id is required"}

        async with self._db_session_factory() as db:
            # Get document
            doc = await db.get(Document, document_id)
            if doc is None:
                return {"error": "Document not found"}

            # Get document links
            link_stmt = select(DocumentLink).where(
                (DocumentLink.source_document_id == document_id)
                | (DocumentLink.target_document_id == document_id)
            )
            link_result = await db.execute(link_stmt)
            links = link_result.scalars().all()

            doc_links = []
            for link in links:
                linked_id = link.target_document_id if link.source_document_id == document_id else link.source_document_id
                linked_doc = await db.get(Document, linked_id)
                doc_links.append({
                    "linked_document_id": linked_id,
                    "linked_document_title": linked_doc.title if linked_doc else "Unknown",
                    "link_type": link.link_type,
                    "is_manual": link.is_manual,
                    "description": link.description or "",
                })

            # Get order links
            odl_stmt = select(OrderDocumentLink).where(OrderDocumentLink.document_id == document_id)
            odl_result = await db.execute(odl_stmt)
            od_links = odl_result.scalars().all()

            order_links = []
            for odl in od_links:
                order = await db.get(Order, odl.order_id)
                order_links.append({
                    "order_id": odl.order_id,
                    "order_title": order.title if order else "Unknown",
                    "order_number": order.order_number or "",
                    "link_type": odl.link_type,
                    "description": odl.description or "",
                })

            return {
                "document_id": doc.id,
                "document_title": doc.title,
                "document_links": doc_links,
                "order_links": order_links,
                "total_relations": len(doc_links) + len(order_links),
            }

    async def generate_draft(self, params: dict) -> dict:
        """Generate a draft document from context."""
        from app.services.generator_service import generator_service

        context = params.get("context", "")
        holding_id = params.get("holding_id")

        if not context:
            return {"error": "context is required"}

        try:
            # We need a db session; create a minimal one
            from app.database import async_session

            async with async_session() as db:
                result = await generator_service.generate(
                    context=context,
                    holding_id=holding_id,
                    user_id=None,  # System user
                    db=db,
                )
                return {
                    "document_id": result.get("document_id"),
                    "title": result.get("title", ""),
                    "status": result.get("status", "draft"),
                    "message": "Draft document generated successfully",
                }
        except Exception as e:
            logger.exception("generate_draft failed")
            return {"error": f"Generation failed: {str(e)}"}


# ─── Main Server Loop ──────────────────────────────────────────────

async def run_mcp_server() -> None:
    """
    Main MCP server loop.

    Reads JSON-RPC 2.0 requests from stdin, dispatches to tools,
    and writes responses to stdout.
    """
    handler = MCPToolHandler()

    # Set up db session factory
    from app.database import async_session
    handler.set_db_session_factory(lambda: async_session)

    # Write server capabilities on startup
    capabilities = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "srp-mcp-server",
                "version": "0.1.0",
            },
        },
    }
    # Note: MCP protocol initial handshake may vary; we send capabilities as first message
    # In strict MCP, the client sends 'initialize' first.

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            response = json_rpc_error(None, -32700, f"Parse error: {e}")
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
            continue

        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            response = json_rpc_result(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "srp-mcp-server", "version": "0.1.0"},
            })
        elif method == "tools/list":
            response = json_rpc_result(req_id, {"tools": TOOL_DEFINITIONS})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                tool_fn = getattr(handler, tool_name, None)
                if tool_fn is None:
                    response = json_rpc_error(req_id, -32601, f"Tool not found: {tool_name}")
                else:
                    result = await tool_fn(tool_args)
                    response = json_rpc_result(req_id, result)
            except Exception as e:
                logger.exception("Error executing tool %s", tool_name)
                response = json_rpc_error(req_id, -32603, f"Internal error: {str(e)}")
        elif method == "notifications/initialized":
            # No response needed for notifications
            continue
        else:
            response = json_rpc_error(req_id, -32601, f"Method not found: {method}")

        sys.stdout.write(response + "\n")
        sys.stdout.flush()


def main() -> None:
    """Entry point for the MCP server process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting SRP MCP server...")

    import asyncio
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
