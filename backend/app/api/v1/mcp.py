"""
MCP HTTP Router — JSON-RPC 2.0 over HTTP + SSE.
Exposes AI-agent tools for internal and external consumption.
"""
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.services.pattern_analysis_service import pattern_analysis_service
from app.services.generator_service import generator_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ─── JSON-RPC 2.0 Helpers ──────────────────────────────────────────

def rpc_error(id_: Any, code: int, message: str, data: Any = None) -> dict:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "error": error, "id": id_}


def rpc_result(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "result": result, "id": id_}


# ─── Tool Handlers ─────────────────────────────────────────────────

async def handle_get_holding_profile(params: dict, db: AsyncSession) -> dict:
    """Get holding profile."""
    from app.models.holding import Holding

    holding_id = params.get("holding_id")
    stmt = select(Holding)
    if holding_id:
        stmt = stmt.where(Holding.id == holding_id)
    else:
        stmt = stmt.limit(1)
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


async def handle_search_documents(params: dict, db: AsyncSession) -> dict:
    """Search documents."""
    from app.models.document import Document

    query = params.get("query", "")
    status = params.get("status")
    holding_id = params.get("holding_id")
    page = params.get("page", 1)
    page_size = params.get("page_size", 20)

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

    count_stmt = stmt.with_only_columns(Document.id)
    count_result = await db.execute(count_stmt)
    total = len(count_result.scalars().all())

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
                "was_analyzed": d.was_analyzed,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ],
    }


async def handle_get_document_relationships(params: dict, db: AsyncSession) -> dict:
    """Get impact map."""
    from app.models.document import Document
    from app.services.impact_service import impact_service

    document_id = params.get("document_id")
    if not document_id:
        return {"error": "document_id is required"}

    # Get document holding_id
    doc = await db.get(Document, document_id)
    if doc is None:
        return {"error": "Document not found"}

    try:
        impact = await impact_service.get_impact_map(document_id, doc.holding_id, db)
        return impact.model_dump(mode="json")
    except Exception as e:
        logger.exception("get_document_relationships failed")
        return {"error": str(e)}


async def handle_generate_draft(params: dict, db: AsyncSession) -> dict:
    """Generate a draft document."""
    from app.models.user import User
    from app.models.holding import Holding

    context = params.get("context", "")
    holding_id = params.get("holding_id")

    if not context:
        return {"error": "context is required"}

    try:
        if holding_id:
            stmt = select(Holding).where(Holding.id == holding_id)
        else:
            stmt = select(Holding).limit(1)
        result = await db.execute(stmt)
        holding = result.scalar_one_or_none()
        if holding is None:
            return {"error": "No holding found"}

        # Get admin user for system generation
        stmt = select(User).limit(1)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            return {"error": "No user found"}

        # Temporarily set active_holding for system user
        if user.active_holding_id is None:
            user.active_holding_id = holding.id

        doc_response = await generator_service.generate(
            context_description=context,
            user=user,
            holding_id=holding.id,
            db=db,
        )

        return {
            "document_id": doc_response.id,
            "title": doc_response.title,
            "status": doc_response.status,
            "stats": doc_response.stats.model_dump() if hasattr(doc_response, 'stats') else {},
            "message": "Draft generated successfully",
        }
    except Exception as e:
        logger.exception("generate_draft failed")
        return {"error": f"Generation failed: {str(e)}"}


async def handle_analyze_document(params: dict, db: AsyncSession) -> dict:
    """Analyze an approved document for patterns."""
    document_id = params.get("document_id")
    if not document_id:
        return {"error": "document_id is required"}

    try:
        result = await pattern_analysis_service.analyze_document(
            document_id=document_id,
            db=db,
        )
        return result
    except Exception as e:
        logger.exception("analyze_document failed")
        return {"error": str(e)}


async def handle_get_holding_patterns(params: dict, db: AsyncSession) -> dict:
    """Get extracted patterns for a holding."""
    from app.models.holding import Holding

    holding_id = params.get("holding_id")
    stmt = select(Holding)
    if holding_id:
        stmt = stmt.where(Holding.id == holding_id)
    else:
        stmt = stmt.limit(1)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()
    if holding is None:
        return {"error": "Holding not found"}

    return {
        "id": holding.id,
        "name": holding.name,
        "document_structure": holding.document_structure or {},
        "style_settings": holding.style_settings or {},
        "analysis_count": (holding.style_settings or {}).get("documents_analyzed", 0),
    }


async def handle_learn_from_documents(params: dict, db: AsyncSession) -> dict:
    """Analyze multiple approved documents to learn patterns."""
    from app.models.document import Document

    holding_id = params.get("holding_id")
    document_ids = params.get("document_ids", [])

    if not holding_id and not document_ids:
        return {"error": "Provide holding_id or document_ids"}

    # Find approved documents
    stmt = select(Document)
    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))
    if holding_id:
        stmt = stmt.where(Document.holding_id == holding_id)
    stmt = stmt.where(Document.status == "approved").where(Document.was_analyzed.is_(False))

    result = await db.execute(stmt)
    docs = result.scalars().all()

    if not docs:
        return {"message": "No unanalyzed approved documents found", "analyzed": 0}

    results = []
    for doc in docs:
        try:
            analysis = await pattern_analysis_service.analyze_document(doc.id, db)
            results.append({"document_id": doc.id, "title": doc.title, "status": "analyzed"})
        except Exception as e:
            results.append({"document_id": doc.id, "title": doc.title, "status": "error", "error": str(e)})

    return {
        "analyzed": len([r for r in results if r["status"] == "analyzed"]),
        "errors": len([r for r in results if r["status"] == "error"]),
        "results": results,
    }


# ─── Tool Definitions ──────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_holding_profile",
        "description": "Get holding profile with structure and style settings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "holding_id": {"type": "integer", "description": "Holding ID (optional)"},
            },
        },
    },
    {
        "name": "search_documents",
        "description": "Search documents in the registry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "status": {"type": "string", "description": "Filter by status"},
                "holding_id": {"type": "integer", "description": "Holding ID filter"},
                "page": {"type": "integer", "description": "Page number"},
                "page_size": {"type": "integer", "description": "Items per page"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_document_relationships",
        "description": "Get impact map for a document.",
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
        "description": "Generate a draft document from context description.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {"type": "string", "description": "Description of what the document should regulate"},
                "holding_id": {"type": "integer", "description": "Holding ID for template"},
            },
            "required": ["context"],
        },
    },
    {
        "name": "analyze_document",
        "description": "Analyze an approved document for structural and style patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "integer", "description": "Document ID to analyze"},
            },
            "required": ["document_id"],
        },
    },
    {
        "name": "get_holding_patterns",
        "description": "Get extracted style/structure patterns for a holding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "holding_id": {"type": "integer", "description": "Holding ID (optional)"},
            },
        },
    },
    {
        "name": "learn_from_documents",
        "description": "Analyze multiple approved documents to learn holding patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "holding_id": {"type": "integer", "description": "Holding ID"},
                "document_ids": {"type": "array", "items": {"type": "integer"}, "description": "Specific document IDs"},
            },
        },
    },
]

# Map tool names to handler functions
TOOL_HANDLERS = {
    "get_holding_profile": handle_get_holding_profile,
    "search_documents": handle_search_documents,
    "get_document_relationships": handle_get_document_relationships,
    "generate_draft": handle_generate_draft,
    "analyze_document": handle_analyze_document,
    "get_holding_patterns": handle_get_holding_patterns,
    "learn_from_documents": handle_learn_from_documents,
}


# ─── Routes ────────────────────────────────────────────────────────

TOOLS_LIST_RESPONSE = {"tools": TOOL_DEFINITIONS}


@router.post("", include_in_schema=True)
async def mcp_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
    """JSON-RPC 2.0 endpoint for MCP tools."""
    try:
        body = await request.json()
    except Exception:
        return rpc_error(None, -32700, "Parse error")

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "tools/list":
        return rpc_result(req_id, TOOLS_LIST_RESPONSE)

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return rpc_error(req_id, -32601, f"Tool not found: {tool_name}")

        try:
            result = await handler(tool_args, db)
            return rpc_result(req_id, result)
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            return rpc_error(req_id, -32603, f"Internal error: {str(e)}")

    return rpc_error(req_id, -32601, f"Method not found: {method}")


@router.get("/tools", include_in_schema=True)
async def list_mcp_tools():
    """List available MCP tools (GET version for easy discovery)."""
    return TOOLS_LIST_RESPONSE


@router.get("/stream")
async def mcp_stream():
    """SSE endpoint for streaming MCP events."""
    async def event_generator():
        yield f"data: {json.dumps({'type': 'connected', 'message': 'MCP stream connected'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
