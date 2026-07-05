#!/usr/bin/env python3
"""
Session Complete Hook for OpenCode.

Runs after each session completes. Stores session summary
into the MCP Memory Server as knowledge graph entities.

Installed via opencode.json experimental.hook.session_completed.
"""

import sqlite3
import json
import os
import sys
from datetime import datetime

DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
MEMORY_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "mcp_memory_helper.py")


def get_last_session():
    """Get the most recently updated session from the DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, agent, model, time_created, time_updated,
               summary_files, summary_additions, summary_deletions,
               (SELECT COUNT(*) FROM message WHERE session_id = session.id) as msg_count
        FROM session
        ORDER BY time_updated DESC
        LIMIT 1
    """)
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "title": row[1] or "(untitled)",
        "agent": row[2] or "",
        "model": row[3] or "",
        "time_created": row[4],
        "time_updated": row[5],
        "files": row[6] or 0,
        "additions": row[7] or 0,
        "deletions": row[8] or 0,
        "messages": row[9] or 0
    }


def store_in_memory(session):
    """Store session info into MCP Memory Server via its helper."""
    if not os.path.exists(MEMORY_SERVER_SCRIPT):
        return False
    
    # Create a temporary JSON-RPC message to the MCP memory server
    # We use the Python MCP client approach
    try:
        import subprocess
        result = subprocess.run(
            ["python", MEMORY_SERVER_SCRIPT, json.dumps(session)],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"  Memory store error: {e}", file=sys.stderr)
        return False


def main():
    session = get_last_session()
    if not session:
        print("No sessions found", file=sys.stderr)
        return
    
    title = session["title"]
    agent = session["agent"]
    msgs = session["messages"]
    
    print(f"Session completed: {title} ({agent}, {msgs} msgs)")
    
    # Try to store in memory server
    stored = store_in_memory(session)
    if stored:
        print(f"  -> Stored in MCP Memory Server")
    else:
        print(f"  -> Memory server not available")


if __name__ == "__main__":
    main()
