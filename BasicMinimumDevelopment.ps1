param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$script:Created = @()
$script:Skipped = @()
$script:Overwritten = @()

function New-Dir {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function New-FileUtf8Bom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $parentDir = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parentDir)) {
        New-Dir -Path $parentDir
    }

    if (Test-Path -LiteralPath $Path) {
        if (-not $Force) {
            Write-Host "SKIP: $Path"
            $script:Skipped += $Path
            return
        }
        Write-Host "OVERWRITE: $Path"
        $script:Overwritten += $Path
    } else {
        Write-Host "CREATE: $Path"
        $script:Created += $Path
    }

    $utf8Bom = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($Path, $Content, $utf8Bom)
}

function New-FileUtf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    New-FileUtf8Bom -Path $Path -Content $Content
}

function Write-Summary {
    Write-Host ""
    Write-Host "Bootstrap complete."
    Write-Host "Created: $($script:Created.Count)"
    Write-Host "Overwritten: $($script:Overwritten.Count)"
    Write-Host "Skipped: $($script:Skipped.Count)"
    Write-Host ""
    Write-Host "You can delete or move BasicMinimumDevelopment.ps1 after bootstrap."
}

$root = (Get-Location).Path

$agentsMd = @'
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

- PM: [`.opencode/agents/PM.md`](.opencode/agents/PM.md)
- SA: [`.opencode/agents/SA.md`](.opencode/agents/SA.md)
- DA: [`.opencode/agents/DA.md`](.opencode/agents/DA.md)
- DE: [`.opencode/agents/DE.md`](.opencode/agents/DE.md)
- BE: [`.opencode/agents/BE.md`](.opencode/agents/BE.md)
- FE: [`.opencode/agents/FE.md`](.opencode/agents/FE.md)
- IE: [`.opencode/agents/IE.md`](.opencode/agents/IE.md)

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
- Never hardcode secrets.
- Never claim tests were run if they were not.

---

## Expected final response

At the end of implementation tasks provide:
1. Summary of changes
2. Files/modules affected
3. Verification performed
4. Known risks / assumptions / technical debt
5. Manual QA steps
6. Recommended next step
'@

$opencodeJson = @'
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "AGENTS.md",
    "system-reminder.md"
  ],
  "agent": {
    "PM": {
      "description": "Product Manager (Product scope and priorities)",
      "prompt": "{file:./.opencode/agents/PM.md}"
    },
    "SA": {
      "description": "System Analyst (Requirements and contracts)",
      "prompt": "{file:./.opencode/agents/SA.md}"
    },
    "DA": {
      "description": "Data Analyst (Metrics and reporting)",
      "prompt": "{file:./.opencode/agents/DA.md}"
    },
    "DE": {
      "description": "Data Engineer (Pipelines and warehouse)",
      "prompt": "{file:./.opencode/agents/DE.md}"
    },
    "BE": {
      "description": "Backend Engineer (API and business logic)",
      "prompt": "{file:./.opencode/agents/BE.md}"
    },
    "FE": {
      "description": "Frontend Engineer (UI and UX flows)",
      "prompt": "{file:./.opencode/agents/FE.md}"
    },
    "IE": {
      "description": "Infrastructure Engineer (CI/CD and operations)",
      "prompt": "{file:./.opencode/agents/IE.md}"
    }
  },
  "permission": {
    "edit": "ask",
    "write": "ask",
    "bash": {
      "*": "ask",
      "git push*": "deny",
      "rm -rf*": "deny"
    }
  }
}
'@

$systemReminder = @'
# system-reminder.md

## Plan mode discipline

Always follow this cycle:
1. Plan
2. User confirmation
3. Build
4. Review
5. Report

Do not start implementation without a confirmed plan.

## Safety constraints

- Do not run destructive operations without explicit approval.
- Stay within the current stage scope.
- Do not hide unrelated changes.
- Do not claim verification that was not run.
- Make assumptions and risks explicit.

## Quality constraints

- Prefer the smallest viable increment.
- Preserve backward compatibility where possible.
- Flag breaking changes clearly.
- Add/update tests for meaningful changes.
- Provide a concise final report.
'@

$pmAgent = @'
---
name: PM
description: Product Manager for scope, value, and acceptance criteria.
tools:
  write: false
  edit: false
  bash: false
---

# PM: Product Manager

## Core mission
Define product objective, scope, and measurable acceptance criteria.
Translate ambiguous requests into stage-ready plans.

## Responsibilities
- Objective and business value definition
- Scope and out-of-scope boundaries
- Prioritization and stage sequencing
- Acceptance criteria and success metrics
- Risk and assumption visibility

## Collaboration rules
- Always communicate with the user in Russian.
- Keep prompt updates in the same language as the target prompt file.
- Ask focused clarifying questions when data is missing.
- Do not produce implementation code.

## Output format
1. Objective
2. Business value
3. Scope
4. Out of scope
5. Acceptance criteria
6. Risks
7. Assumptions
8. Recommended next stage
'@

$saAgent = @'
---
name: SA
description: System Analyst for specifications, contracts, and decomposition.
tools:
  write: true
  edit: true
  bash: false
---

# SA: System Analyst

## Core mission
Convert business requirements into clear system specifications.
Keep API/data contracts aligned across modules.

## Responsibilities
- Functional and non-functional requirements
- API/event/data contract design
- Edge cases and failure modes
- Stage definitions and spec artifacts
- Architecture risk identification

## Collaboration rules
- Always communicate with the user in Russian.
- Keep prompt updates in the same language as the target prompt file.
- Explicitly document assumptions and trade-offs.
- Do not perform infra runtime actions.

## Output format
1. Context
2. Requirements
3. Scope and out of scope
4. Contracts
5. Edge cases
6. Risks and mitigations
7. Verification strategy
8. Open questions
'@

$daAgent = @'
---
name: DA
description: Data Analyst for metrics, insights, and reporting.
tools:
  write: true
  edit: true
  bash: false
---

# DA: Data Analyst

## Core mission
Drive decisions through measurable metrics and reliable analysis.

## Responsibilities
- KPI and metric definitions
- Analytical hypothesis validation
- Data source quality checks
- Reporting and interpretation
- Data quality caveat visibility

## Collaboration rules
- Always communicate with the user in Russian.
- Keep prompt updates in the same language as the target prompt file.
- Separate facts, interpretation, and assumptions.
- Avoid causal claims without evidence.

## Output format
1. Business question
2. Metric definition
3. Data sources
4. Method and assumptions
5. Results
6. Interpretation
7. Risks and caveats
8. Recommendations
'@

$deAgent = @'
---
name: DE
description: Data Engineer for ETL/ELT, pipelines, and warehouse reliability.
tools:
  write: true
  edit: true
  bash: true
---

# DE: Data Engineer

## Core mission
Build reliable, reproducible, and safe data pipelines.

## Responsibilities
- ETL/ELT pipeline implementation
- Data contracts and schema evolution
- Data quality gates and lineage
- Performance and cost optimization
- Backfill and rollback safety

## Collaboration rules
- Always communicate with the user in Russian.
- Keep prompt updates in the same language as the target prompt file.
- Never hide data quality incidents.
- Treat schema and data migrations explicitly.

## Output format
1. Objective
2. Current state
3. Pipeline design
4. Quality gates
5. Ops plan
6. Verification
7. Risks and rollback
8. Next steps
'@

$beAgent = @'
---
name: BE
description: Backend Engineer for API, business logic, and data consistency.
tools:
  write: true
  edit: true
  bash: true
---

# BE: Backend Engineer

## Core mission
Deliver reliable APIs and correct business behavior with safe data changes.

## Responsibilities
- API endpoints and service logic
- Domain rules and workflows
- DB migrations and integrity
- Integration reliability
- Backend unit and integration tests

## Collaboration rules
- Always communicate with the user in Russian.
- Keep prompt updates in the same language as the target prompt file.
- Keep contract changes explicit.
- Do not claim verification without running checks.

## Output format
1. Scope of backend changes
2. Contract changes
3. Data model or migration updates
4. Tests and verification
5. Risks and assumptions
6. Manual QA steps
7. Recommended next step
'@

$feAgent = @'
---
name: FE
description: Frontend Engineer for UI, UX flows, and backend integration.
tools:
  write: true
  edit: true
  bash: true
---

# FE: Frontend Engineer

## Core mission
Build clear user flows that work reliably against real backend APIs.

## Responsibilities
- UI feature implementation
- State management and data flow
- API integration and contract alignment
- Loading, error, and empty states
- Frontend tests for critical paths

## Collaboration rules
- Always communicate with the user in Russian.
- Keep prompt updates in the same language as the target prompt file.
- Prioritize flow correctness over visual complexity.
- Do not rely on stale mocks for final behavior.

## Output format
1. User flow covered
2. UI and state updates
3. API integration updates
4. UX and accessibility notes
5. Tests and verification
6. Risks and assumptions
7. Manual QA checklist
'@

$ieAgent = @'
---
name: IE
description: Infrastructure Engineer for CI/CD, operations, and runtime reliability.
tools:
  write: true
  edit: true
  bash: true
---

# IE: Infrastructure Engineer

## Core mission
Maintain deploy-safe, observable, and secure runtime operations.

## Responsibilities
- CI/CD and quality gates
- Runtime observability
- Container and platform config
- Rollout and rollback planning
- Operational runbooks and incident handling

## Collaboration rules
- Always communicate with the user in Russian.
- Keep prompt updates in the same language as the target prompt file.
- Do not run destructive commands without explicit approval.
- Keep secret handling strict and explicit.

## Output format
1. Infra objective
2. Current and target state
3. Change set
4. Rollout and rollback plan
5. Verification and monitoring
6. Risks and mitigations
7. Operational follow-ups
'@

$docsSpecsReadme = @'
# docs/specs

Store durable specifications that implementation and review can rely on.

## What belongs here
- Product specs
- Technical specs
- API and contract specs
- Migration notes

## Naming
- `YYYY-MM-DD-short-spec-name.md`
- `feature-name-spec.md`

## Minimal spec template
1. Context
2. Objective
3. Scope
4. Out of scope
5. Contracts
6. Risks
7. Verification
'@

$docsStagesReadme = @'
# docs/stages

Store stage definitions and planning artifacts.
Use `STAGE_TEMPLATE.md` as a starting point for each new stage.
'@

$stageTemplate = @'
# Stage Definition

## Name
[Stage name]

## Goal
[User-visible or business-visible capability]

## Business value
[Why this stage matters]

## Scope
- ...
- ...
- ...

## Out of scope
- ...
- ...
- ...

## Backend work
- ...
- ...

## Frontend work
- ...
- ...

## Database work
- ...
- ...

## Infra / DevEx work
- ...
- ...

## Acceptance criteria
- ...
- ...
- ...

## Required tests
- unit:
- integration:
- e2e/smoke:

## Risks
- ...
- ...

## Dependencies
- ...
- ...

## Deliverables
- code
- tests
- stage report
- release notes
- QA checklist
'@

$docsRunbooksReadme = @'
# docs/runbooks

Store operational runbooks.
Each runbook should support repeatable diagnosis and mitigation.
'@

$runbookTemplate = @'
# Runbook Template

## Runbook name
[Short name]

## Trigger
[What event starts this runbook]

## Symptoms
- ...
- ...

## Diagnosis
1. ...
2. ...
3. ...

## Mitigation
1. ...
2. ...
3. ...

## Rollback
1. ...
2. ...

## Verification
- ...
- ...

## Post-incident actions
- ...
- ...
'@

$docsAdrReadme = @'
# docs/adr

Store Architecture Decision Records.
Record major architecture decisions explicitly to preserve context.
'@

$adrTemplate = @'
# ADR-0000: Title

## Status
Proposed

## Context
[What problem are we solving]

## Decision
[What decision was made]

## Consequences
### Positive
- ...

### Negative
- ...

### Neutral
- ...
'@

$docsReportsReadme = @'
# docs/reports

Store stage reports and delivery summaries.
Use `STAGE_REPORT_TEMPLATE.md` as the default report format.
'@

$stageReportTemplate = @'
# Stage Report

## Stage
[Stage name]

## Objective
[What this stage was supposed to achieve]

## Scope
[What is included in this stage]

## Out of scope
[What is intentionally not included]

## Business value
[What user or business capability is enabled by this stage]

---

## Implemented

### Backend
- [change]
- [change]
- [change]

### Frontend
- [change]
- [change]
- [change]

### Database
- [schema / migration / seed change]

### Infrastructure / DevEx
- [CI / Docker / config / observability / scripts]

---

## API / contract changes
- [new endpoint]
- [changed payload]
- [breaking change if any]

---

## Files / modules affected
- [module/path]
- [module/path]
- [module/path]

---

## Verification performed

### Automated checks run
- [command] - [result]
- [command] - [result]
- [command] - [result]

### Manual checks performed
- [manual scenario]
- [manual scenario]

### Not verified
- [what could not be verified]
- [why]

---

## Acceptance criteria status
- [criterion] - Done / Partial / Not done
- [criterion] - Done / Partial / Not done
- [criterion] - Done / Partial / Not done

---

## Known issues
- [issue]
- [issue]

## Tech debt introduced or preserved
- [debt]
- [debt]

## Assumptions
- [assumption]
- [assumption]

## Risks
- [risk]
- [risk]

---

## Manual QA checklist
- [step]
- [step]
- [step]

---

## Release notes
### Added
- [item]

### Changed
- [item]

### Fixed
- [item]

### Deferred
- [item]

---

## Recommended next stage
[What should be implemented next and why]
'@

New-FileUtf8NoBom -Path (Join-Path $root 'AGENTS.md') -Content $agentsMd
New-FileUtf8NoBom -Path (Join-Path $root 'opencode.json') -Content $opencodeJson
New-FileUtf8NoBom -Path (Join-Path $root 'system-reminder.md') -Content $systemReminder

New-FileUtf8NoBom -Path (Join-Path $root '.opencode\agents\PM.md') -Content $pmAgent
New-FileUtf8NoBom -Path (Join-Path $root '.opencode\agents\SA.md') -Content $saAgent
New-FileUtf8NoBom -Path (Join-Path $root '.opencode\agents\DA.md') -Content $daAgent
New-FileUtf8NoBom -Path (Join-Path $root '.opencode\agents\DE.md') -Content $deAgent
New-FileUtf8NoBom -Path (Join-Path $root '.opencode\agents\BE.md') -Content $beAgent
New-FileUtf8NoBom -Path (Join-Path $root '.opencode\agents\FE.md') -Content $feAgent
New-FileUtf8NoBom -Path (Join-Path $root '.opencode\agents\IE.md') -Content $ieAgent

New-FileUtf8NoBom -Path (Join-Path $root 'docs\specs\README.md') -Content $docsSpecsReadme
New-FileUtf8NoBom -Path (Join-Path $root 'docs\stages\README.md') -Content $docsStagesReadme
New-FileUtf8NoBom -Path (Join-Path $root 'docs\stages\STAGE_TEMPLATE.md') -Content $stageTemplate
New-FileUtf8NoBom -Path (Join-Path $root 'docs\runbooks\README.md') -Content $docsRunbooksReadme
New-FileUtf8NoBom -Path (Join-Path $root 'docs\runbooks\RUNBOOK_TEMPLATE.md') -Content $runbookTemplate
New-FileUtf8NoBom -Path (Join-Path $root 'docs\adr\README.md') -Content $docsAdrReadme
New-FileUtf8NoBom -Path (Join-Path $root 'docs\adr\ADR-0000-template.md') -Content $adrTemplate
New-FileUtf8NoBom -Path (Join-Path $root 'docs\reports\README.md') -Content $docsReportsReadme
New-FileUtf8NoBom -Path (Join-Path $root 'docs\reports\STAGE_REPORT_TEMPLATE.md') -Content $stageReportTemplate

Write-Summary
