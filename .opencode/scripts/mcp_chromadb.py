#!/usr/bin/env python3
"""
MCP Server for ChromaDB Session Search.

Provides tools for agents to search past OpenCode sessions.
Uses the ChromaDB index created by index_sessions.py.

Register with OpenCode:
  opencode mcp add (interactive) or add to opencode.json:
  "mcp": {
    "chromadb": {
      "type": "local",
      "command": ["python", ".opencode/scripts/mcp_chromadb.py"]
    }
  }
"""

import os
import sys
import json
from datetime import datetime

# Ensure we're in the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Configuration
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chromadb")
COLLECTION_NAME = "opencode_sessions"
OLLAMA_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"

# Import after potential path setup
from mcp.server.fastmcp import FastMCP
import chromadb
from chromadb.config import Settings
import requests

# Create MCP server
mcp = FastMCP(
    "ChromaDB Session Search",
    instructions="Search across past OpenCode sessions by semantic similarity. Use this to find relevant past work, decisions, and context."
)


def get_chroma_collection():
    """Get or create the ChromaDB collection."""
    if not os.path.exists(CHROMA_DIR):
        return None
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False)
    )
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return None


def get_embedding(text: str) -> list[float]:
    """Get embedding from Ollama."""
    resp = requests.post(OLLAMA_URL, json={
        "model": EMBED_MODEL,
        "input": text
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


@mcp.tool()
def search_sessions(query: str, limit: int = 10) -> str:
    """
    Search past OpenCode sessions by semantic similarity.
    
    Args:
        query: The search query describing what you're looking for
        limit: Maximum number of results (default 10, max 50)
    
    Returns:
        Formatted list of matching sessions with scores and metadata
    """
    collection = get_chroma_collection()
    if collection is None:
        return "❌ ChromaDB index not found. Run `python .opencode/scripts/index_sessions.py` first."
    
    limit = min(max(limit, 1), 50)
    
    try:
        query_emb = get_embedding(query)
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=limit
        )
    except Exception as e:
        return f"❌ Search error: {e}"
    
    if not results["ids"][0]:
        return f"No sessions found for: '{query}'"
    
    lines = [f"🔍 Search results for: '{query}'", f"   Found {len(results['ids'][0])} sessions\n"]
    
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        score = 1.0 - (distance / 2.0)
        
        title = meta.get("title", "(no title)")
        agent = meta.get("agent", "?")
        project = meta.get("project_name", "?")
        time_str = meta.get("time_created_str", "?")
        msgs = meta.get("message_count", "?")
        
        lines.append(f"  [{i+1}] Score: {score:.3f}")
        lines.append(f"       Title: {title}")
        lines.append(f"       Agent: {agent} | Project: {project} | Messages: {msgs}")
        lines.append(f"       Date: {time_str}")
        lines.append(f"       Session: {meta.get('session_id', '?')}")
        lines.append("")
    
    return "\n".join(lines)


@mcp.tool()
def get_index_stats() -> str:
    """
    Get statistics about the ChromaDB session index.
    
    Returns:
        Number of indexed sessions, location, embedding model info
    """
    collection = get_chroma_collection()
    if collection is None:
        return "❌ ChromaDB index not found."
    
    count = collection.count()
    return (
        f"📊 ChromaDB Session Index\n"
        f"   Documents: {count} sessions\n"
        f"   Embedding: {EMBED_MODEL} (768 dim)\n"
        f"   Location: {CHROMA_DIR}\n"
        f"   Ready for semantic search."
    )


@mcp.tool()
def get_session_by_id(session_id: str) -> str:
    """
    Get details of a specific session by its ID.
    
    Args:
        session_id: The session ID (e.g., 'ses_abc123...')
    
    Returns:
        Session metadata and title
    """
    collection = get_chroma_collection()
    if collection is None:
        return "❌ ChromaDB index not found."
    
    try:
        # ChromaDB ids are stored with "ses_" prefix  
        doc_id = session_id if session_id.startswith("ses_") else f"ses_{session_id}"
        results = collection.get(ids=[doc_id])
    except Exception as e:
        return f"❌ Error: {e}"
    
    if not results["ids"]:
        return f"Session '{session_id}' not found in index."
    
    meta = results["metadatas"][0]
    doc = results["documents"][0]
    
    return (
        f"📄 Session: {meta.get('session_id', session_id)}\n"
        f"   Title: {meta.get('title', '(no title)')}\n"
        f"   Agent: {meta.get('agent', '?')} | Model: {meta.get('model', '?')}\n"
        f"   Project: {meta.get('project_name', '?')}\n"
        f"   Created: {meta.get('time_created_str', '?')}\n"
        f"   Messages: {meta.get('message_count', 0)}\n"
        f"   Files changed: {meta.get('summary_files', 0)}\n"
        f"   Index text: {doc}"
    )


@mcp.tool()
def search_by_project(project_name: str, limit: int = 10) -> str:
    """
    Filter sessions by project name using metadata filter.
    
    Args:
        project_name: Project name to filter by
        limit: Maximum results (default 10)
    
    Returns:
        List of sessions in the specified project
    """
    collection = get_chroma_collection()
    if collection is None:
        return "❌ ChromaDB index not found."
    
    limit = min(max(limit, 1), 50)
    
    try:
        results = collection.get(
            where={"project_name": project_name},
            limit=limit
        )
    except Exception as e:
        return f"❌ Search error: {e}"
    
    if not results["ids"]:
        return f"No sessions found for project '{project_name}'."
    
    lines = [f"📁 Project: '{project_name}' ({len(results['ids'])} sessions)\n"]
    
    for i in range(len(results["ids"])):
        meta = results["metadatas"][i]
        lines.append(f"  [{i+1}] {meta.get('title', '(no title)')}")
        lines.append(f"       Agent: {meta.get('agent', '?')} | Date: {meta.get('time_created_str', '?')}")
        lines.append(f"       Messages: {meta.get('message_count', 0)} | ID: {meta.get('session_id', '?')}")
        lines.append("")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Run with stdio transport (for MCP)
    mcp.run(transport="stdio")
