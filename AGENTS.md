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

- PM: [`.opencode/agents/PM.md`](.opencode/agents/PM.md) — основной агент для общения с пользователем
- SA: [`.opencode/agents/SA.md`](.opencode/agents/SA.md) — скрыт из UI, доступен для делегирования
- DA: [`.opencode/agents/DA.md`](.opencode/agents/DA.md) — скрыт из UI, доступен для делегирования
- DE: [`.opencode/agents/DE.md`](.opencode/agents/DE.md) — скрыт из UI, доступен для делегирования
- BE: [`.opencode/agents/BE.md`](.opencode/agents/BE.md) — скрыт из UI, доступен для делегирования
- FE: [`.opencode/agents/FE.md`](.opencode/agents/FE.md) — скрыт из UI, доступен для делегирования
- IE: [`.opencode/agents/IE.md`](.opencode/agents/IE.md) — скрыт из UI, доступен для делегирования

В UI выбора отображаются только **Plan**, **Build** и **PM**.
Остальные агенты вызываются главным агентом (PM) через внутреннее делегирование.

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