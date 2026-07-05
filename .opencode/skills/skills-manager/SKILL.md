---
name: skills-manager
description: Analyze project plan and determine which skills (.opencode/skills/*/SKILL.md) are needed. Delegate creation of missing skills to SA. NEVER ask the user.
compatibility: opencode
metadata:
  audience: pm
  workflow: planning, skills
---

# Skills Manager

## Mission
PM loads this skill during project planning. Your job: analyze the project plan, technology stack, and stage requirements to determine which skills are needed, then ensure they are installed.

## Analysis Protocol

### Step 1: Read project state
Check what already exists:
- `opencode.json` — project configuration
- `.opencode/skills/` — currently installed skills
- `.opencode/agents/*.md` — available agents
- `package.json`, `pyproject.toml`, `requirements.txt`, `Cargo.toml` — tech stack

### Step 2: Determine needed skills
Map project characteristics to skills:

| If project has | Install skill | Reason |
|---|---|---|
| Any code | code-review | Always needed for quality |
| Tests or test files | test-driven | Ensures test coverage |
| Complex architecture (3+ modules) | arch-review | Catches design issues early |
| External API calls | api-tester | Validates contracts |
| Database schema | db-schema | Documents data model |
| Docker/deployment | infra-check | Reviews ops config |
| UI components | ui-review | Checks UX consistency |
| Documentation directory | docs-generator | Auto-generates docs |
| Python project | python-helper | Python-specific patterns |
| Node.js project | node-helper | JS/TS-specific patterns |
| Python project (FastAPI, Flask, Django) | python-helper | Python-specific patterns |
| Complex architecture (3+ modules, pipeline) | arch-review | Catches design issues early |
| Database models (SQLAlchemy, SQLite, Postgres) | db-schema | Documents data model |
| API endpoints (REST, FastAPI routes) | api-tester | Validates contracts |

### Step 3: Compare with installed skills
- Read `.opencode/skills/` directory listing
- For each missing recommended skill, add to install list
- For installed skills not matching current project, mark as optional

### Step 4: Delegate installation
Delegate to SA (System Analyst) with:
1. List of skills to create (name + description + content)
2. Path: `.opencode/skills/<name>/SKILL.md`
3. SA has write access and will create the files

### Step 5: Update manifest
Ensure `.opencode/skills/skills-manifest.json` reflects current state:
```json
{
  "version": "1",
  "skills": [
    {"name": "grill-me", "auto": true, "reason": "default"},
    {"name": "code-review", "auto": true, "reason": "universal"}
  ]
}
```

## Important
- NEVER ask the user which skills to install
- NEVER skip skills analysis
- ALWAYS delegate file creation to SA (PM cannot write files)
