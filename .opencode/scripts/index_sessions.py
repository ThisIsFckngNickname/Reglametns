#!/usr/bin/env python3
"""
ChromaDB Session Indexer for OpenCode

Indexes session titles and metadata from the OpenCode SQLite database
into ChromaDB with embeddings from Ollama (nomic-embed-text).

Usage:
    python index_sessions.py          # Index all sessions
    python index_sessions.py --query "search terms"  # Search indexed sessions
"""

import sqlite3
import json
import time
import os
import sys
import argparse
from datetime import datetime

# Configuration
DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chromadb")
OLLAMA_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "nomic-embed-text"
COLLECTION_NAME = "opencode_sessions"
BATCH_SIZE = 10  # Number of sessions to embed in one batch


def get_ollama_embedding(text: str) -> list[float]:
    """Get embedding vector from Ollama."""
    import requests
    resp = requests.post(OLLAMA_URL, json={
        "model": EMBED_MODEL,
        "input": text
    }, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["embeddings"][0]


def get_ollama_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Get embedding vectors for multiple texts in one batch."""
    import requests
    resp = requests.post(OLLAMA_URL, json={
        "model": EMBED_MODEL,
        "input": texts
    }, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["embeddings"]


def get_sessions(cursor, limit=None, offset=0):
    """Fetch sessions from database."""
    query = """
        SELECT 
            s.id, s.project_id, s.title, s.agent, s.model,
            s.time_created, s.time_updated,
            s.summary_files, s.summary_additions, s.summary_deletions,
            s.metadata,
            (SELECT COUNT(*) FROM message m WHERE m.session_id = s.id) as message_count,
            p.name as project_name
        FROM session s
        LEFT JOIN project p ON s.project_id = p.id
        ORDER BY s.time_created DESC
    """
    if limit:
        query += f" LIMIT {limit} OFFSET {offset}"
    
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def make_document_text(session: dict) -> str:
    """Create searchable text from session data."""
    parts = []
    if session["title"]:
        parts.append(session["title"])
    if session["agent"]:
        parts.append(f"Agent: {session['agent']}")
    if session["project_name"]:
        parts.append(f"Project: {session['project_name']}")
    if session["model"]:
        parts.append(f"Model: {session['model']}")
    return " | ".join(parts)


def make_metadata(session: dict) -> dict:
    """Create metadata dict for ChromaDB."""
    return {
        "session_id": session["id"],
        "project_id": session["project_id"] or "",
        "project_name": session["project_name"] or "",
        "title": session["title"] or "",
        "agent": session["agent"] or "",
        "model": session["model"] or "",
        "time_created": session["time_created"] or 0,
        "time_created_str": datetime.fromtimestamp(
            (session["time_created"] or 0) / 1000
        ).strftime("%Y-%m-%d %H:%M") if session["time_created"] else "",
        "message_count": session["message_count"] or 0,
        "summary_files": session["summary_files"] or 0,
        "summary_additions": session["summary_additions"] or 0,
        "summary_deletions": session["summary_deletions"] or 0,
    }


def index_sessions(force=False):
    """Index all sessions into ChromaDB."""
    import chromadb
    from chromadb.config import Settings
    
    print(f"Connecting to DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM session")
    total = cursor.fetchone()[0]
    print(f"Total sessions in DB: {total}")
    
    # Setup ChromaDB
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # Get or create collection
    try:
        collection = client.get_collection(COLLECTION_NAME)
        existing_count = collection.count()
        print(f"Existing collection '{COLLECTION_NAME}' has {existing_count} documents")
        
        if not force and existing_count > 0:
            print("Collection already exists. Use --force to re-index.")
            conn.close()
            return existing_count
        
        if force:
            print("Re-indexing: deleting existing collection...")
            client.delete_collection(COLLECTION_NAME)
            collection = client.create_collection(COLLECTION_NAME)
    except Exception:
        collection = client.create_collection(COLLECTION_NAME)
        print(f"Created new collection '{COLLECTION_NAME}'")
    
    # Fetch all sessions
    sessions = get_sessions(cursor)
    total = len(sessions)
    print(f"Indexing {total} sessions...")
    
    # Process in batches
    indexed = 0
    for i in range(0, total, BATCH_SIZE):
        batch = sessions[i:i + BATCH_SIZE]
        
        # Prepare documents and metadata
        documents = [make_document_text(s) for s in batch]
        ids = [f"ses_{s['id']}" for s in batch]
        metadatas = [make_metadata(s) for s in batch]
        
        # Get embeddings
        try:
            embeddings = get_ollama_embeddings_batch(documents)
        except Exception as e:
            print(f"  Error getting embeddings at session {i}: {e}")
            print(f"  Trying one-by-one...")
            embeddings = []
            for doc in documents:
                try:
                    emb = get_ollama_embedding(doc)
                    embeddings.append(emb)
                except Exception as e2:
                    print(f"  Skipping: {e2}")
                    embeddings.append([0.0] * 768)  # Placeholder
        
        # Add to ChromaDB
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        
        indexed += len(batch)
        print(f"  Progress: {indexed}/{total} ({indexed*100//total}%)")
    
    conn.close()
    print(f"\n✅ Indexing complete: {indexed} sessions indexed")
    print(f"   ChromaDB location: {CHROMA_DIR}")
    return indexed


def search_sessions(query: str, n_results: int = 10):
    """Search indexed sessions."""
    import chromadb
    from chromadb.config import Settings
    
    if not os.path.exists(CHROMA_DIR):
        print(f"❌ ChromaDB not found at {CHROMA_DIR}")
        print("   Run 'python index_sessions.py' first to build the index.")
        return []
    
    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False)
    )
    
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        print(f"❌ Collection '{COLLECTION_NAME}' not found")
        return []
    
    print(f"Searching for: '{query}'")
    print(f"Index size: {collection.count()} documents\n")
    
    # Get query embedding
    query_embedding = get_ollama_embedding(query)
    
    # Search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )
    
    if not results["ids"][0]:
        print("No results found.")
        return []
    
    print(f"{'ID':40s} {'Score':8s} {'Title'}")
    print("-" * 100)
    
    output = []
    for i in range(len(results["ids"][0])):
        doc_id = results["ids"][0][i]
        distance = results["distances"][0][i] if "distances" in results else 0
        metadata = results["metadatas"][0][i]
        document = results["documents"][0][i]
        
        score = 1.0 - (distance / 2.0)  # Normalize to ~0-1
        title = metadata.get("title", "")[:60]
        
        print(f"{doc_id:40s} {score:.4f}  {title}")
        
        output.append({
            "id": doc_id,
            "score": score,
            "title": metadata.get("title", ""),
            "agent": metadata.get("agent", ""),
            "project": metadata.get("project_name", ""),
            "time": metadata.get("time_created_str", ""),
            "messages": metadata.get("message_count", 0),
            "text": document
        })
    
    return output


def main():
    parser = argparse.ArgumentParser(description="ChromaDB Session Indexer for OpenCode")
    parser.add_argument("--query", "-q", help="Search query")
    parser.add_argument("--force", "-f", action="store_true", help="Force re-index")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Number of search results")
    parser.add_argument("--info", action="store_true", help="Show index info")
    
    args = parser.parse_args()
    
    if args.info:
        import chromadb
        from chromadb.config import Settings
        if os.path.exists(CHROMA_DIR):
            client = chromadb.PersistentClient(path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False))
            try:
                collection = client.get_collection(COLLECTION_NAME)
                print(f"Collection: {COLLECTION_NAME}")
                print(f"Documents: {collection.count()}")
                print(f"Location: {CHROMA_DIR}")
                print(f"Embedding model: {EMBED_MODEL} (768 dim)")
            except Exception:
                print("No collection found. Run without --info to index.")
        else:
            print("No ChromaDB found at:", CHROMA_DIR)
        return
    
    if args.query:
        search_sessions(args.query, args.limit)
    else:
        index_sessions(force=args.force)


if __name__ == "__main__":
    main()
