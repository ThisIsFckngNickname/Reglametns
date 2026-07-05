#!/usr/bin/env python3
"""
MCP Memory Helper - stores session info into the MCP Memory Server.
Called by session_complete_hook.py with session JSON as argument.
Uses the MCP client library to communicate with the memory server.
"""

import sys
import json
import asyncio

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("MCP library not available", file=sys.stderr)
    sys.exit(1)


async def store_session(session: dict):
    """Store session as entity in memory server."""
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session_client:
            await session_client.initialize()
            
            # Create entity for this session
            entity_name = session["title"][:80]  # Truncate long titles
            entity_id = session["id"]
            
            observations = [
                f"Agent: {session['agent']}",
                f"Model: {session['model']}",
                f"Messages: {session['messages']}",
                f"Files changed: {session['files']}",
                f"Additions: {session['additions']}",
                f"Deletions: {session['deletions']}",
            ]
            
            result = await session_client.call_tool("create_entities", {
                "entities": [{
                    "name": entity_name,
                    "entityType": "session",
                    "observations": observations
                }]
            })
            
            print(f"Created entity: {entity_name}", file=sys.stderr)
            return True


def main():
    if len(sys.argv) < 2:
        print("Usage: mcp_memory_helper.py <session_json>", file=sys.stderr)
        sys.exit(1)
    
    session = json.loads(sys.argv[1])
    success = asyncio.run(store_session(session))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
