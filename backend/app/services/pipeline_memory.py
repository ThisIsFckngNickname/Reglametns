"""
pipeline_memory — MCP Memory integration for paragraph analysis pipeline.

Stores analysis results and profiles as entities in the knowledge graph
via @modelcontextprotocol/server-memory.

Usage:
    store = MemoryStore()
    await store.store_analysis(profile_id, stats, doc_count)
    await store.store_profile(profile_id, profile_dict)
    await store.close()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# Default memory server location — project root
# The MCP server supports MEMORY_FILE_PATH env var (since server-memory 0.x)
# We set it to write memory.jsonl in the project root.
MEMORY_SERVER_COMMAND = "npx"
MEMORY_SERVER_ARGS = ["-y", "@modelcontextprotocol/server-memory"]

# Project root is 4 levels up from this file:
#   backend/app/services/pipeline_memory.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_MEMORY_FILE_PATH = str(_PROJECT_ROOT / "memory.jsonl")


class MemoryStore:
    """
    MCP Memory Store for pipeline results.

    Manages a connection to the @modelcontextprotocol/server-memory
    and stores/retrieves entities related to document analysis.

    The memory.jsonl file is written to the project root directory.
    """

    def __init__(self, server_command: str = MEMORY_SERVER_COMMAND,
                 server_args: list[str] = None):
        self.server_params = StdioServerParameters(
            command=server_command,
            args=server_args or MEMORY_SERVER_ARGS,
            env={
                "MEMORY_FILE_PATH": _MEMORY_FILE_PATH,
                **os.environ,
            },
            cwd=str(_PROJECT_ROOT),
        )
        self._session: Optional[ClientSession] = None
        self._context = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to the MCP Memory server. Returns True if successful."""
        try:
            self._context = stdio_client(self.server_params)
            self._read, self._write = await self._context.__aenter__()
            self._session = await ClientSession(self._read, self._write).__aenter__()
            await self._session.initialize()
            self._connected = True
            logger.info("Connected to MCP Memory Server")
            return True
        except Exception as e:
            logger.warning("Failed to connect to MCP Memory Server: %s", e)
            self._connected = False
            return False

    async def close(self):
        """Close the connection to the MCP Memory server."""
        if self._session:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._context:
            await self._context.__aexit__(None, None, None)
            self._context = None
        self._connected = False
        logger.info("Disconnected from MCP Memory Server")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def ensure_connected(self) -> bool:
        """Connect if not already connected."""
        if not self._connected:
            return await self.connect()
        return True

    async def store_analysis(
        self,
        profile_id: str,
        stats: dict[str, Any],
        document_count: int = 1,
    ) -> bool:
        """
        Store an analysis result as an entity in the knowledge graph.

        Args:
            profile_id: UUID of the profile
            stats: Statistics dict from compute_stats()
            document_count: Number of documents analyzed

        Returns:
            True if stored successfully
        """
        if not await self.ensure_connected():
            return False

        try:
            entity_name = f"Analysis:{profile_id[:8]}"
            observations = [
                f"profile_id: {profile_id}",
                f"document_count: {document_count}",
                f"timestamp: {datetime.now().isoformat()}",
            ]
            if stats:
                observations.append(
                    f"stats: total_paragraphs={stats.get('total_paragraphs', 0)}, "
                    f"total_steps={stats.get('total_steps', 0)}, "
                    f"parse_errors={stats.get('parse_error_count', 0)}"
                )

            await self._session.call_tool("create_entities", {
                "entities": [{
                    "name": entity_name,
                    "entityType": "document_analysis",
                    "observations": observations,
                }]
            })
            logger.info("Stored analysis entity: %s", entity_name)
            return True
        except Exception as e:
            logger.warning("Failed to store analysis: %s", e)
            return False

    async def store_profile(
        self,
        profile_id: str,
        profile: dict[str, Any],
    ) -> bool:
        """
        Store a synthesized paragraph profile as an entity.

        Args:
            profile_id: UUID of the profile
            profile: Dict representation of ParagraphLogicProfile

        Returns:
            True if stored successfully
        """
        if not await self.ensure_connected():
            return False

        try:
            entity_name = f"Profile:{profile_id[:8]}"
            observations = [
                f"profile_id: {profile_id}",
                f"version: {profile.get('version', 2)}",
                f"total_steps_analyzed: {profile.get('total_steps_analyzed', 0)}",
                f"source_document_count: {profile.get('source_document_count', 0)}",
                f"timestamp: {datetime.now().isoformat()}",
            ]

            # Add template summary
            templates = profile.get('step_templates', [])
            if templates:
                observations.append(f"step_templates: {len(templates)} templates")
                for i, t in enumerate(templates[:3], 1):
                    observations.append(f"  template_{i}: {t[:120]}")

            # Add vocabulary summary
            vocab = profile.get('vocabulary', {})
            if vocab:
                roles = vocab.get('roles', {})
                actions = vocab.get('actions', {})
                observations.append(
                    f"vocabulary: {len(roles)} roles, {len(actions)} actions"
                )

            # Add logic rules summary
            rules = profile.get('logic_rules', {})
            if rules:
                observations.append(f"logic_rules: {json.dumps(rules, ensure_ascii=False)}")

            await self._session.call_tool("create_entities", {
                "entities": [{
                    "name": entity_name,
                    "entityType": "paragraph_profile",
                    "observations": observations,
                }]
            })

            # Create relation between analysis and profile if analysis exists
            analysis_name = f"Analysis:{profile_id[:8]}"
            await self._session.call_tool("create_relations", {
                "relations": [{
                    "from": analysis_name,
                    "to": entity_name,
                    "relationType": "produced_profile",
                }]
            })

            logger.info("Stored profile entity: %s", entity_name)
            return True
        except Exception as e:
            logger.warning("Failed to store profile: %s", e)
            return False

    async def store_step_statistics(
        self,
        profile_id: str,
        steps: list[dict],
    ) -> bool:
        """
        Store step statistics from the profile as observations
        on the existing analysis entity.

        Args:
            profile_id: UUID of the profile
            steps: List of step dicts (from statistical_fallback or LLM)
        """
        if not await self.ensure_connected():
            return False

        # Group steps by role for summary
        role_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        for s in steps:
            role = s.get("role") or "unknown"
            action = s.get("action") or "unknown"
            role_counts[role] = role_counts.get(role, 0) + 1
            action_counts[action] = action_counts.get(action, 0) + 1

        top_roles = sorted(role_counts.items(), key=lambda x: -x[1])[:5]
        top_actions = sorted(action_counts.items(), key=lambda x: -x[1])[:5]

        entity_name = f"Analysis:{profile_id[:8]}"

        try:
            observations = [
                f"top_roles: {', '.join(f'{r}({c})' for r, c in top_roles)}",
                f"top_actions: {', '.join(f'{a}({c})' for a, c in top_actions)}",
                f"total_unique_roles: {len(role_counts)}",
                f"total_unique_actions: {len(action_counts)}",
            ]

            await self._session.call_tool("add_observations", {
                "observations": [
                    {"entityName": entity_name, "observations": observations}
                ]
            })

            logger.info("Stored step statistics for: %s", entity_name)
            return True
        except Exception as e:
            logger.warning("Failed to store step statistics: %s", e)
            return False

    async def search_analyses(self, query: str = "") -> list[dict]:
        """Search for analysis/profile entities in the knowledge graph."""
        if not await self.ensure_connected():
            return []

        try:
            result = await self._session.call_tool("search_nodes", {
                "query": query,
            })
            # The result is a list of text contents
            if hasattr(result, 'content'):
                raw = result.content[0].text if result.content else "[]"
                return json.loads(raw)
            return []
        except Exception as e:
            logger.warning("Search failed: %s", e)
            return []

    async def read_graph(self) -> dict:
        """Read the entire knowledge graph."""
        if not await self.ensure_connected():
            return {}

        try:
            result = await self._session.call_tool("read_graph", {})
            if hasattr(result, 'content'):
                raw = result.content[0].text if result.content else "{}"
                return json.loads(raw)
            return {}
        except Exception as e:
            logger.warning("Read graph failed: %s", e)
            return {}


# ─── Convenience functions ─────────────────────────────────────────


async def store_pipeline_result(
    profile_id: str,
    stats: dict[str, Any],
    profile_dict: dict[str, Any],
    document_count: int = 1,
) -> dict[str, bool]:
    """
    Store the complete pipeline result in MCP Memory.

    This is a one-shot convenience function that:
    1. Connects to memory server
    2. Stores the analysis
    3. Stores the profile
    4. Stores step statistics (if steps dict with role/action data)
    5. Disconnects

    Args:
        profile_id: UUID of the profile
        stats: Statistics from compute_stats()
        profile_dict: Dict representation of ParagraphLogicProfile
        document_count: Number of documents analyzed

    Returns:
        Dict with keys: analysis_stored, profile_stored
    """
    result = {"analysis_stored": False, "profile_stored": False}

    try:
        async with MemoryStore() as store:
            result["analysis_stored"] = await store.store_analysis(
                profile_id, stats, document_count
            )
            result["profile_stored"] = await store.store_profile(
                profile_id, profile_dict
            )
    except Exception as e:
        logger.error("Failed to store pipeline result: %s", e)

    return result


if __name__ == "__main__":
    """Self-test: stores a dummy profile and reads back the graph."""
    import asyncio

    async def test():
        store = MemoryStore()
        connected = await store.connect()
        print(f"Connected: {connected}")

        if connected:
            # Store a test analysis
            test_stats = {
                "total_paragraphs": 10,
                "total_steps": 25,
                "parse_error_count": 1,
            }
            ok = await store.store_analysis(
                "test-profile-001", test_stats, document_count=2
            )
            print(f"Analysis stored: {ok}")

            # Store a test profile
            test_profile = {
                "version": 2,
                "total_steps_analyzed": 25,
                "source_document_count": 2,
                "step_templates": [
                    "[Должность] [действие] в срок [срок]",
                ],
                "vocabulary": {
                    "roles": {"Начальник": 5, "Бухгалтер": 3},
                    "actions": {"осуществляет": 4, "составляет": 3},
                },
                "logic_rules": {
                    "role_required": True,
                    "deadline_required": False,
                },
            }
            ok = await store.store_profile("test-profile-001", test_profile)
            print(f"Profile stored: {ok}")

            # Read graph
            graph = await store.read_graph()
            print(f"\nKnowledge Graph entities: {len(graph.get('entities', []))}")
            for e in graph.get("entities", []):
                print(f"  - {e.get('name')} ({e.get('entityType')})")

            await store.close()

        print("\nDone!")

    asyncio.run(test())
