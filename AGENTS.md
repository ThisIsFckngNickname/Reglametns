# AGENTS.md

## Purpose
This repository uses AI-assisted workflows in OpenCode.
Agents working in this repo must prioritize:
- correctness
- maintainability
- explicit architecture
- testability
- safe incremental delivery
- business value per stage

Do not treat this repo as a one-shot generation task.
Work in small, reviewable increments.

---

## Working model

### Default execution model
For any non-trivial task:
1. Start with a plan.
2. Limit scope to the current stage only.
3. Implement the minimum viable increment.
4. Run relevant verification.
5. Produce a concise change report.

Do not perform broad uncontrolled rewrites unless explicitly requested.

### Stage discipline
Work must be organized into stages.
Each stage should:
- produce demonstrable value
- be testable
- be reviewable
- have clear acceptance criteria
- have clear out-of-scope boundaries

### End-to-end preference
Prefer vertical slices over layer-by-layer delivery.
For product features, prefer backend + frontend + DB + integration + tests in one stage.

---

## Roles and routing

- PM: [`.opencode/agents/PM.md`](.opencode/agents/PM.md) РІР‚вЂќ Р С•РЎРѓР Р…Р С•Р Р†Р Р…Р С•Р в„– Р В°Р С–Р ВµР Р…РЎвЂљ Р Т‘Р В»РЎРЏ Р С•Р В±РЎвЂ°Р ВµР Р…Р С‘РЎРЏ РЎРѓ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»Р ВµР С
- SA: [`.opencode/agents/SA.md`](.opencode/agents/SA.md) РІР‚вЂќ РЎРѓР С”РЎР‚РЎвЂ№РЎвЂљ Р С‘Р В· UI, Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… Р Т‘Р В»РЎРЏ Р Т‘Р ВµР В»Р ВµР С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ
- DA: [`.opencode/agents/DA.md`](.opencode/agents/DA.md) РІР‚вЂќ РЎРѓР С”РЎР‚РЎвЂ№РЎвЂљ Р С‘Р В· UI, Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… Р Т‘Р В»РЎРЏ Р Т‘Р ВµР В»Р ВµР С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ
- DE: [`.opencode/agents/DE.md`](.opencode/agents/DE.md) РІР‚вЂќ РЎРѓР С”РЎР‚РЎвЂ№РЎвЂљ Р С‘Р В· UI, Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… Р Т‘Р В»РЎРЏ Р Т‘Р ВµР В»Р ВµР С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ
- BE: [`.opencode/agents/BE.md`](.opencode/agents/BE.md) РІР‚вЂќ РЎРѓР С”РЎР‚РЎвЂ№РЎвЂљ Р С‘Р В· UI, Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… Р Т‘Р В»РЎРЏ Р Т‘Р ВµР В»Р ВµР С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ
- FE: [`.opencode/agents/FE.md`](.opencode/agents/FE.md) РІР‚вЂќ РЎРѓР С”РЎР‚РЎвЂ№РЎвЂљ Р С‘Р В· UI, Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… Р Т‘Р В»РЎРЏ Р Т‘Р ВµР В»Р ВµР С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ
- IE: [`.opencode/agents/IE.md`](.opencode/agents/IE.md) РІР‚вЂќ РЎРѓР С”РЎР‚РЎвЂ№РЎвЂљ Р С‘Р В· UI, Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р… Р Т‘Р В»РЎРЏ Р Т‘Р ВµР В»Р ВµР С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ

Р вЂ™ UI Р Р†РЎвЂ№Р В±Р С•РЎР‚Р В° Р С•РЎвЂљР С•Р В±РЎР‚Р В°Р В¶Р В°РЎР‹РЎвЂљРЎРѓРЎРЏ РЎвЂљР С•Р В»РЎРЉР С”Р С• **Plan**, **Build** Р С‘ **PM**.
Р С›РЎРѓРЎвЂљР В°Р В»РЎРЉР Р…РЎвЂ№Р Вµ Р В°Р С–Р ВµР Р…РЎвЂљРЎвЂ№ Р Р†РЎвЂ№Р В·РЎвЂ№Р Р†Р В°РЎР‹РЎвЂљРЎРѓРЎРЏ Р С–Р В»Р В°Р Р†Р Р…РЎвЂ№Р С Р В°Р С–Р ВµР Р…РЎвЂљР С•Р С (PM) РЎвЂЎР ВµРЎР‚Р ВµР В· Р Р†Р Р…РЎС“РЎвЂљРЎР‚Р ВµР Р…Р Р…Р ВµР Вµ Р Т‘Р ВµР В»Р ВµР С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘Р Вµ.

Routing examples:
- discovery, scope, prioritization -> PM
- specs and contracts -> SA
- metrics and reporting -> DA
- pipelines and warehouse -> DE
- APIs and business logic -> BE
- UI and user flows -> FE
- CI/CD and operations -> IE

---

## Subagent prompt evolution

The main agent should periodically improve subagent prompts:
- Trigger review on user request or after every 3-5 significant stages.
- Capture recurring mistakes, missing constraints, and better output formats.
- Update `AGENTS.md` and relevant files in `.opencode/agents/`.
- Apply prompt edits in the same language as each target prompt file.
- Keep changes small, explicit, and versioned in commit history.
- Do not change role scope without documenting why.

Prompt update process:
1. Identify quality gaps from recent tasks.
2. Propose prompt diff and expected behavior change.
3. Get user confirmation for non-trivial changes.
4. Apply updates and run a small validation task.

---

## Planning rules

Before large or risky changes, produce a plan with:
- objective
- scope
- out of scope
- impacted modules
- data model changes
- API changes
- frontend changes
- risks
- verification strategy
- rollout/migration notes

If ambiguous, choose the simplest extensible design and state assumptions clearly.

---

## Quality and safety rules

- Prefer simple explicit code over clever abstractions.
- Respect module boundaries and avoid circular dependencies.
- Minimize blast radius and avoid unnecessary rewrites.
- Preserve backward compatibility unless breaking change is approved.
- **Check .opencode/lessons.md** before implementing — document contains known issues and their fixes. Search it for relevant keywords before starting any task.
- Never hardcode secrets.

### СЂСџвЂќТ‘ Р вЂ“Р РѓР РЋР СћР С™Р ВР в„ў Р вЂ”Р С’Р СџР В Р вЂўР Сћ: Р С—Р С•Р Т‘Р Т‘Р ВµР В»Р С”Р В° РЎвЂљР ВµРЎРѓРЎвЂљР С•Р Р†

**Р В¤Р В°Р В±РЎР‚Р С‘Р С”Р В°РЎвЂ Р С‘РЎРЏ РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљР С•Р Р† РЎвЂљР ВµРЎРѓРЎвЂљР С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ РІР‚вЂќ Р С–РЎР‚РЎС“Р В±Р ВµР в„–РЎв‚¬Р ВµР Вµ Р Р…Р В°РЎР‚РЎС“РЎв‚¬Р ВµР Р…Р С‘Р Вµ, Р Р†Р ВµР Т‘РЎС“РЎвЂ°Р ВµР Вµ Р С” Р С—Р ВµРЎР‚Р ВµРЎРѓР СР С•РЎвЂљРЎР‚РЎС“ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В°.**

Р вЂ”Р В°Р С—РЎР‚Р ВµРЎвЂ°Р В°Р ВµРЎвЂљРЎРѓРЎРЏ:
1. **Р Р€РЎвЂљР Р†Р ВµРЎР‚Р В¶Р Т‘Р В°РЎвЂљРЎРЉ РЎвЂЎРЎвЂљР С• РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚ Р В·Р В°Р С—РЎС“РЎвЂ°Р ВµР Р…/РЎР‚Р В°Р В±Р С•РЎвЂљР В°Р ВµРЎвЂљ** Р В±Р ВµР В· РЎвЂћР В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С•Р С–Р С• `curl http://localhost:PORT/` Р С‘ Р С—Р С•Р С”Р В°Р В·Р В° Р Р†РЎвЂ№Р Р†Р С•Р Т‘Р В°
2. **Р Р€РЎвЂљР Р†Р ВµРЎР‚Р В¶Р Т‘Р В°РЎвЂљРЎРЉ РЎвЂЎРЎвЂљР С• РЎвЂћР В°Р в„–Р В» РЎРѓР С•Р В·Р Т‘Р В°Р Р…** Р В±Р ВµР В· `dir <Р С—РЎС“РЎвЂљРЎРЉ>` / `ls -la <Р С—РЎС“РЎвЂљРЎРЉ>` Р С‘ Р С—Р С•Р С”Р В°Р В·Р В° Р Р†РЎвЂ№Р Р†Р С•Р Т‘Р В°
3. **Р Р€РЎвЂљР Р†Р ВµРЎР‚Р В¶Р Т‘Р В°РЎвЂљРЎРЉ РЎвЂЎРЎвЂљР С• API Р Р†Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ X** Р В±Р ВµР В· `curl -v` Р С‘ Р С—Р С•Р С”Р В°Р В·Р В° Р С—Р С•Р В»Р Р…Р С•Р С–Р С• response
4. **Р вЂњР С•Р Р†Р С•РЎР‚Р С‘РЎвЂљРЎРЉ Р’В«Р С”Р С•Р Т‘ РЎР‚Р В°Р В±Р С•РЎвЂљР В°Р ВµРЎвЂљ/Р Р…Р Вµ РЎР‚Р В°Р В±Р С•РЎвЂљР В°Р ВµРЎвЂљР’В»** Р В±Р ВµР В· Р В·Р В°Р С—РЎС“РЎРѓР С”Р В° Р С‘ Р С—Р С•Р С”Р В°Р В·Р В° Р С•РЎв‚¬Р С‘Р В±Р С”Р С‘/РЎР‚Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљР В°
5. **Р ВРЎРѓР С—РЎР‚Р В°Р Р†Р В»РЎРЏРЎвЂљРЎРЉ Р В±Р В°Р С– Р С‘ Р Р…Р Вµ Р С—Р ВµРЎР‚Р ВµР В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљРЎРЉ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С”РЎС“** РІР‚вЂќ Р С”Р В°Р В¶Р Т‘Р С•Р Вµ Р С‘РЎРѓР С—РЎР‚Р В°Р Р†Р В»Р ВµР Р…Р С‘Р Вµ = Р Р…Р С•Р Р†Р В°РЎРЏ Р Р†Р ВµРЎР‚Р С‘РЎвЂћР С‘Р С”Р В°РЎвЂ Р С‘РЎРЏ

Р СћРЎР‚Р ВµР В±Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ:
1. Р С™Р В°Р В¶Р Т‘Р С•Р Вµ РЎС“РЎвЂљР Р†Р ВµРЎР‚Р В¶Р Т‘Р ВµР Р…Р С‘Р Вµ Р С• РЎР‚Р В°Р В±Р С•РЎвЂљР С•РЎРѓР С—Р С•РЎРѓР С•Р В±Р Р…Р С•РЎРѓРЎвЂљР С‘ Р Т‘Р С•Р В»Р В¶Р Р…Р С• Р С—Р С•Р Т‘Р С”РЎР‚Р ВµР С—Р В»РЎРЏРЎвЂљРЎРЉРЎРѓРЎРЏ Р Р†РЎвЂ№Р Р†Р С•Р Т‘Р С•Р С РЎР‚Р ВµР В°Р В»РЎРЉР Р…Р С•Р в„– Р С”Р С•Р СР В°Р Р…Р Т‘РЎвЂ№
2. Р СџР С•РЎРѓР В»Р Вµ Р С‘Р СР С—Р В»Р ВµР СР ВµР Р…РЎвЂљР В°РЎвЂ Р С‘Р С‘ Stage РІР‚вЂќ Р Р†РЎвЂ№Р В·Р Р†Р В°РЎвЂљРЎРЉ QA-Р В°Р С–Р ВµР Р…РЎвЂљР В° Р Т‘Р В»РЎРЏ Р Р…Р ВµР В·Р В°Р Р†Р С‘РЎРѓР С‘Р СР С•Р в„– Р Р†Р ВµРЎР‚Р С‘РЎвЂћР С‘Р С”Р В°РЎвЂ Р С‘Р С‘
3. QA-Р В°Р С–Р ВµР Р…РЎвЂљ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµРЎвЂљ Р вЂ™Р РЋР вЂў Acceptance Criteria Р С‘Р В· РЎРѓР С—Р ВµРЎвЂ Р С‘РЎвЂћР С‘Р С”Р В°РЎвЂ Р С‘Р С‘ SA
4. Р СћР С•Р В»РЎРЉР С”Р С• Р С—Р С•РЎРѓР В»Р Вµ Р С—Р С•Р Т‘РЎвЂљР Р†Р ВµРЎР‚Р В¶Р Т‘Р ВµР Р…Р С‘РЎРЏ QA Stage РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµРЎвЂљРЎРѓРЎРЏ Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬РЎвЂР Р…Р Р…РЎвЂ№Р С
5. Р вЂ™РЎРѓР Вµ РЎвЂљР ВµРЎРѓРЎвЂљРЎвЂ№ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎР‹РЎвЂљРЎРѓРЎРЏ Р Р…Р В° РЎвЂЎР С‘РЎРѓРЎвЂљР С•Р С РЎРѓР С•РЎРѓРЎвЂљР С•РЎРЏР Р…Р С‘Р С‘ (РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚ Р С—Р ВµРЎР‚Р ВµР В·Р В°Р С—РЎС“РЎвЂ°Р ВµР Р…, РЎвЂљР ВµРЎРѓРЎвЂљР С•Р Р†РЎвЂ№Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ РЎС“Р Т‘Р В°Р В»Р ВµР Р…РЎвЂ№)

### РІСљвЂ¦ Р СџРЎР‚Р С•РЎвЂ Р ВµРЎРѓРЎРѓ Р Р†Р ВµРЎР‚Р С‘РЎвЂћР С‘Р С”Р В°РЎвЂ Р С‘Р С‘ (Р С•Р В±РЎРЏР В·Р В°РЎвЂљР ВµР В»Р ВµР Р… Р Т‘Р В»РЎРЏ Р С”Р В°Р В¶Р Т‘Р С•Р С–Р С• Stage):
1. Р В Р В°Р В·РЎР‚Р В°Р В±Р С•РЎвЂљРЎвЂЎР С‘Р С” (BE/FE) РЎР‚Р ВµР В°Р В»Р С‘Р В·РЎС“Р ВµРЎвЂљ Р С”Р С•Р Т‘
2. Р В Р В°Р В·РЎР‚Р В°Р В±Р С•РЎвЂљРЎвЂЎР С‘Р С” Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°Р ВµРЎвЂљ РЎвЂљР ВµРЎРѓРЎвЂљРЎвЂ№
3. **QA-Р В°Р С–Р ВµР Р…РЎвЂљ Р С—Р С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ Р В·Р В°Р Т‘Р В°РЎвЂЎРЎС“ Р Р…Р В° Р Р…Р ВµР В·Р В°Р Р†Р С‘РЎРѓР С‘Р СРЎС“РЎР‹ Р Р†Р ВµРЎР‚Р С‘РЎвЂћР С‘Р С”Р В°РЎвЂ Р С‘РЎР‹**
4. QA Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµРЎвЂљ Р С”Р В°Р В¶Р Т‘РЎвЂ№Р в„– Р С—РЎС“Р Р…Р С”РЎвЂљ Acceptance Criteria РЎвЂћР С‘Р В·Р С‘РЎвЂЎР ВµРЎРѓР С”Р С‘Р СР С‘ Р С”Р С•Р СР В°Р Р…Р Т‘Р В°Р СР С‘
5. QA Р Р†РЎвЂ№Р Т‘Р В°РЎвЂРЎвЂљ Р С•РЎвЂљРЎвЂЎРЎвЂРЎвЂљ РЎРѓ Р Т‘Р С•Р С”Р В°Р В·Р В°РЎвЂљР ВµР В»РЎРЉРЎРѓРЎвЂљР Р†Р В°Р СР С‘ (РЎРѓР С”РЎР‚Р С‘Р Р…РЎв‚¬Р С•РЎвЂљРЎвЂ№/Р Р†РЎвЂ№Р Р†Р С•Р Т‘РЎвЂ№ Р С”Р С•Р СР В°Р Р…Р Т‘)
6. Р СћР С•Р В»РЎРЉР С”Р С• Р С—Р С•РЎРѓР В»Р Вµ РІСљвЂ¦ QA Stage РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµРЎвЂљРЎРѓРЎРЏ Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬РЎвЂР Р…Р Р…РЎвЂ№Р С

---

## Expected final response

At the end of implementation tasks provide:
1. Summary of changes
2. Files/modules affected
3. Verification performed
4. Known risks / assumptions / technical debt
5. Manual QA steps
6. Recommended next step

---

## MCP Memory context

This project has **two MCP servers** that store knowledge persistently across sessions:

### 1. memory (`@modelcontextprotocol/server-memory`)
- Stores entities (knowledge graph nodes) with observations
- File: `memory.jsonl` in project root (gitignored)
- Tools available to all agents:
  - `search_nodes(query)` вЂ” search entities by name, type, or observation content
  - `read_graph()` вЂ” read the entire knowledge graph
  - `open_nodes(names)` вЂ” open specific nodes by name
  - `create_entities(...)` вЂ” create new entities
  - `add_observations(...)` вЂ” add observations to existing entities
  - `create_relations(...)` вЂ” create relations between entities
- Contains: document analysis results, paragraph profiles, pipeline statistics
- Written by: `company_profile_routes.py` after profile synthesis

### 2. chromadb (`.opencode/scripts/mcp_chromadb.py`)
- Vector search across all 1513 past OpenCode sessions
- Tools:
  - `search_sessions(query, limit=10)` вЂ” semantic search through session history
  - `get_index_stats()` вЂ” index statistics
  - `get_session_by_id(session_id)` вЂ” get session details
  - `search_by_project(project_name, limit=10)` вЂ” filter by project

### Agent usage rules

1. **Before starting a task**, query relevant context:
   - For project context: `search_nodes("project name or topic")` on memory server
   - For past decisions: `search_sessions("what we discussed about X")` on chromadb
   - For pipeline history: `search_nodes("analysis OR profile")` on memory server

2. **After completing significant work**, store results:
   - Pipeline results are auto-stored by `store_pipeline_result()` in backend code
   - For manual storage: use `create_entities` with entityType describing the content
   - Always include a timestamp observation

3. **Both servers are non-critical**: if they fail, work continues without them.
   The pipeline memory store is wrapped in try/except вЂ” same applies to manual usage.

4. **Data is per-project**: memory.jsonl lives in this project's root.
   Each project has its own knowledge graph.

---

## Dev services startup rules

Р СџРЎР‚Р С‘ Р В·Р В°Р С—РЎС“РЎРѓР С”Р Вµ dev-РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р С•Р Р† (backend uvicorn, frontend Vite) РЎРѓР С•Р В±Р В»РЎР‹Р Т‘Р В°Р в„– РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р С‘Р Вµ Р С—РЎР‚Р В°Р Р†Р С‘Р В»Р В°:

1. **Р вЂ™РЎРѓР Вµ РЎРѓР ВµРЎР‚Р Р†Р С‘РЎРѓРЎвЂ№ Р Т‘Р С•Р В»Р В¶Р Р…РЎвЂ№ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљРЎРЉРЎРѓРЎРЏ Р Р† РЎвЂћР С•Р Р…Р Вµ, Р В±Р ВµР В· Р Р†Р С‘Р Т‘Р С‘Р СРЎвЂ№РЎвЂ¦ Р С•Р С”Р С•Р Р…/Р С”Р С•Р Р…РЎРѓР С•Р В»Р ВµР в„–.**
   - Р вЂќР В»РЎРЏ backend: `Start-Process -WindowStyle Hidden -PassThru -FilePath 'python' -ArgumentList '-m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000' -WorkingDirectory 'backend/'`
   - Р вЂќР В»РЎРЏ frontend: `Start-Process -WindowStyle Hidden -PassThru -FilePath 'cmd.exe' -ArgumentList '/c cd /d \"frontend/\" && npm run dev'`
   - **Р СњР вЂўР вЂєР В¬Р вЂ”Р Р‡** Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљРЎРЉ `UseShellExecute = $true` (Р С•РЎвЂљР С”РЎР‚РЎвЂ№Р Р†Р В°Р ВµРЎвЂљ Р Р…Р С•Р Р†Р С•Р Вµ Р С•Р С”Р Р…Р С•)
   - **Р СњР вЂўР вЂєР В¬Р вЂ”Р Р‡** Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљРЎРЉ python/npm Р Р…Р В°Р С—РЎР‚РЎРЏР СРЎС“РЎР‹ Р В±Р ВµР В· `-WindowStyle Hidden`

2. **Р РЋРЎвЂљР В°Р Р…Р Т‘Р В°РЎР‚РЎвЂљР Р…РЎвЂ№Р Вµ РЎРѓР С”РЎР‚Р С‘Р С—РЎвЂљРЎвЂ№ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В° (Р Т‘Р В»РЎРЏ РЎР‚РЎС“РЎвЂЎР Р…Р С•Р С–Р С• Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ):**
   - `start-dev.ps1` РІР‚вЂќ Р В·Р В°Р С—РЎС“РЎРѓР С” Р С•Р В±Р С•Р С‘РЎвЂ¦ РЎРѓР ВµРЎР‚Р Р†Р С‘РЎРѓР С•Р Р† (РЎРѓР С”РЎР‚РЎвЂ№РЎвЂљРЎвЂ№Р в„– РЎР‚Р ВµР В¶Р С‘Р С)
   - `stop-dev.ps1` РІР‚вЂќ Р С•РЎРѓРЎвЂљР В°Р Р…Р С•Р Р†Р С”Р В° Р С—Р С• PID-РЎвЂћР В°Р в„–Р В»Р В°Р С
   - `start.cmd` РІР‚вЂќ Р В°Р В»РЎРЉРЎвЂљР ВµРЎР‚Р Р…Р В°РЎвЂљР С‘Р Р†Р Р…РЎвЂ№Р в„– Р В·Р В°Р С—РЎС“РЎРѓР С” РЎвЂЎР ВµРЎР‚Р ВµР В· cmd
   - `stop.cmd` РІР‚вЂќ Р С•РЎРѓРЎвЂљР В°Р Р…Р С•Р Р†Р С”Р В° Р С—Р С• Р С—Р С•РЎР‚РЎвЂљР В°Р С

3. **PID-РЎвЂћР В°Р в„–Р В»РЎвЂ№:**
   - Backend: `.backend.pid` (Р Р† Р С”Р С•РЎР‚Р Р…Р Вµ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В°)
   - Frontend: `.frontend.pid` (Р Р† Р С”Р С•РЎР‚Р Р…Р Вµ Р С—РЎР‚Р С•Р ВµР С”РЎвЂљР В°)
   - Р ВРЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“РЎР‹РЎвЂљРЎРѓРЎРЏ Р Т‘Р В»РЎРЏ Р С•РЎРѓРЎвЂљР В°Р Р…Р С•Р Р†Р С”Р С‘ РЎРѓР ВµРЎР‚Р Р†Р С‘РЎРѓР С•Р Р†

4. **Р вЂєР С•Р С–Р С‘:** stdout/stderr РЎРѓР ВµРЎР‚Р Р†Р С‘РЎРѓР С•Р Р† Р Р…Р Вµ Р С—Р ВµРЎР‚Р ВµР Р…Р В°Р С—РЎР‚Р В°Р Р†Р В»РЎРЏРЎР‹РЎвЂљРЎРѓРЎРЏ (Р С‘Р В·-Р В·Р В° Р С•Р С–РЎР‚Р В°Р Р…Р С‘РЎвЂЎР ВµР Р…Р С‘Р в„– PowerShell 5.1 РЎРѓ `-WindowStyle Hidden`). Р СџРЎР‚Р С‘ Р Р…Р ВµР С•Р В±РЎвЂ¦Р С•Р Т‘Р С‘Р СР С•РЎРѓРЎвЂљР С‘ Р В»Р С•Р С–Р С‘РЎР‚Р С•Р Р†Р В°Р Р…Р С‘РЎРЏ Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљРЎРЉ Р Р†РЎР‚РЎС“РЎвЂЎР Р…РЎС“РЎР‹ Р Р† Р Р†Р С‘Р Т‘Р С‘Р СР С•Р С РЎР‚Р ВµР В¶Р С‘Р СР Вµ.

5. **Р СџР С•РЎР‚РЎвЂљРЎвЂ№:** backend Р Р…Р В° 8000, frontend Р Р…Р В° 5173. Р СџР ВµРЎР‚Р ВµР Т‘ Р В·Р В°Р С—РЎС“РЎРѓР С”Р С•Р С Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏРЎвЂљРЎРЉ, РЎвЂЎРЎвЂљР С• Р С—Р С•РЎР‚РЎвЂљРЎвЂ№ РЎРѓР Р†Р С•Р В±Р С•Р Т‘Р Р…РЎвЂ№.
