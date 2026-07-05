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

- PM: [`.opencode/agents/PM.md`](.opencode/agents/PM.md) вЂ” РѕСЃРЅРѕРІРЅРѕР№ Р°РіРµРЅС‚ РґР»СЏ РѕР±С‰РµРЅРёСЏ СЃ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј
- SA: [`.opencode/agents/SA.md`](.opencode/agents/SA.md) вЂ” СЃРєСЂС‹С‚ РёР· UI, РґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РґРµР»РµРіРёСЂРѕРІР°РЅРёСЏ
- DA: [`.opencode/agents/DA.md`](.opencode/agents/DA.md) вЂ” СЃРєСЂС‹С‚ РёР· UI, РґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РґРµР»РµРіРёСЂРѕРІР°РЅРёСЏ
- DE: [`.opencode/agents/DE.md`](.opencode/agents/DE.md) вЂ” СЃРєСЂС‹С‚ РёР· UI, РґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РґРµР»РµРіРёСЂРѕРІР°РЅРёСЏ
- BE: [`.opencode/agents/BE.md`](.opencode/agents/BE.md) вЂ” СЃРєСЂС‹С‚ РёР· UI, РґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РґРµР»РµРіРёСЂРѕРІР°РЅРёСЏ
- FE: [`.opencode/agents/FE.md`](.opencode/agents/FE.md) вЂ” СЃРєСЂС‹С‚ РёР· UI, РґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РґРµР»РµРіРёСЂРѕРІР°РЅРёСЏ
- IE: [`.opencode/agents/IE.md`](.opencode/agents/IE.md) вЂ” СЃРєСЂС‹С‚ РёР· UI, РґРѕСЃС‚СѓРїРµРЅ РґР»СЏ РґРµР»РµРіРёСЂРѕРІР°РЅРёСЏ

Р’ UI РІС‹Р±РѕСЂР° РѕС‚РѕР±СЂР°Р¶Р°СЋС‚СЃСЏ С‚РѕР»СЊРєРѕ **Plan**, **Build** Рё **PM**.
РћСЃС‚Р°Р»СЊРЅС‹Рµ Р°РіРµРЅС‚С‹ РІС‹Р·С‹РІР°СЋС‚СЃСЏ РіР»Р°РІРЅС‹Рј Р°РіРµРЅС‚РѕРј (PM) С‡РµСЂРµР· РІРЅСѓС‚СЂРµРЅРЅРµРµ РґРµР»РµРіРёСЂРѕРІР°РЅРёРµ.

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

### рџ”ґ Р–РЃРЎРўРљРР™ Р—РђРџР Р•Рў: РїРѕРґРґРµР»РєР° С‚РµСЃС‚РѕРІ

**Р¤Р°Р±СЂРёРєР°С†РёСЏ СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ вЂ” РіСЂСѓР±РµР№С€РµРµ РЅР°СЂСѓС€РµРЅРёРµ, РІРµРґСѓС‰РµРµ Рє РїРµСЂРµСЃРјРѕС‚СЂСѓ РїСЂРѕРµРєС‚Р°.**

Р—Р°РїСЂРµС‰Р°РµС‚СЃСЏ:
1. **РЈС‚РІРµСЂР¶РґР°С‚СЊ С‡С‚Рѕ СЃРµСЂРІРµСЂ Р·Р°РїСѓС‰РµРЅ/СЂР°Р±РѕС‚Р°РµС‚** Р±РµР· С„Р°РєС‚РёС‡РµСЃРєРѕРіРѕ `curl http://localhost:PORT/` Рё РїРѕРєР°Р·Р° РІС‹РІРѕРґР°
2. **РЈС‚РІРµСЂР¶РґР°С‚СЊ С‡С‚Рѕ С„Р°Р№Р» СЃРѕР·РґР°РЅ** Р±РµР· `dir <РїСѓС‚СЊ>` / `ls -la <РїСѓС‚СЊ>` Рё РїРѕРєР°Р·Р° РІС‹РІРѕРґР°
3. **РЈС‚РІРµСЂР¶РґР°С‚СЊ С‡С‚Рѕ API РІРѕР·РІСЂР°С‰Р°РµС‚ СЃС‚Р°С‚СѓСЃ X** Р±РµР· `curl -v` Рё РїРѕРєР°Р·Р° РїРѕР»РЅРѕРіРѕ response
4. **Р“РѕРІРѕСЂРёС‚СЊ В«РєРѕРґ СЂР°Р±РѕС‚Р°РµС‚/РЅРµ СЂР°Р±РѕС‚Р°РµС‚В»** Р±РµР· Р·Р°РїСѓСЃРєР° Рё РїРѕРєР°Р·Р° РѕС€РёР±РєРё/СЂРµР·СѓР»СЊС‚Р°С‚Р°
5. **РСЃРїСЂР°РІР»СЏС‚СЊ Р±Р°Рі Рё РЅРµ РїРµСЂРµР·Р°РїСѓСЃРєР°С‚СЊ РїСЂРѕРІРµСЂРєСѓ** вЂ” РєР°Р¶РґРѕРµ РёСЃРїСЂР°РІР»РµРЅРёРµ = РЅРѕРІР°СЏ РІРµСЂРёС„РёРєР°С†РёСЏ

РўСЂРµР±РѕРІР°РЅРёСЏ:
1. РљР°Р¶РґРѕРµ СѓС‚РІРµСЂР¶РґРµРЅРёРµ Рѕ СЂР°Р±РѕС‚РѕСЃРїРѕСЃРѕР±РЅРѕСЃС‚Рё РґРѕР»Р¶РЅРѕ РїРѕРґРєСЂРµРїР»СЏС‚СЊСЃСЏ РІС‹РІРѕРґРѕРј СЂРµР°Р»СЊРЅРѕР№ РєРѕРјР°РЅРґС‹
2. РџРѕСЃР»Рµ РёРјРїР»РµРјРµРЅС‚Р°С†РёРё Stage вЂ” РІС‹Р·РІР°С‚СЊ QA-Р°РіРµРЅС‚Р° РґР»СЏ РЅРµР·Р°РІРёСЃРёРјРѕР№ РІРµСЂРёС„РёРєР°С†РёРё
3. QA-Р°РіРµРЅС‚ РїСЂРѕРІРµСЂСЏРµС‚ Р’РЎР• Acceptance Criteria РёР· СЃРїРµС†РёС„РёРєР°С†РёРё SA
4. РўРѕР»СЊРєРѕ РїРѕСЃР»Рµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ QA Stage СЃС‡РёС‚Р°РµС‚СЃСЏ Р·Р°РІРµСЂС€С‘РЅРЅС‹Рј
5. Р’СЃРµ С‚РµСЃС‚С‹ Р·Р°РїСѓСЃРєР°СЋС‚СЃСЏ РЅР° С‡РёСЃС‚РѕРј СЃРѕСЃС‚РѕСЏРЅРёРё (СЃРµСЂРІРµСЂ РїРµСЂРµР·Р°РїСѓС‰РµРЅ, С‚РµСЃС‚РѕРІС‹Рµ РґР°РЅРЅС‹Рµ СѓРґР°Р»РµРЅС‹)

### вњ… РџСЂРѕС†РµСЃСЃ РІРµСЂРёС„РёРєР°С†РёРё (РѕР±СЏР·Р°С‚РµР»РµРЅ РґР»СЏ РєР°Р¶РґРѕРіРѕ Stage):
1. Р Р°Р·СЂР°Р±РѕС‚С‡РёРє (BE/FE) СЂРµР°Р»РёР·СѓРµС‚ РєРѕРґ
2. Р Р°Р·СЂР°Р±РѕС‚С‡РёРє Р·Р°РїСѓСЃРєР°РµС‚ С‚РµСЃС‚С‹
3. **QA-Р°РіРµРЅС‚ РїРѕР»СѓС‡Р°РµС‚ Р·Р°РґР°С‡Сѓ РЅР° РЅРµР·Р°РІРёСЃРёРјСѓСЋ РІРµСЂРёС„РёРєР°С†РёСЋ**
4. QA РїСЂРѕРІРµСЂСЏРµС‚ РєР°Р¶РґС‹Р№ РїСѓРЅРєС‚ Acceptance Criteria С„РёР·РёС‡РµСЃРєРёРјРё РєРѕРјР°РЅРґР°РјРё
5. QA РІС‹РґР°С‘С‚ РѕС‚С‡С‘С‚ СЃ РґРѕРєР°Р·Р°С‚РµР»СЊСЃС‚РІР°РјРё (СЃРєСЂРёРЅС€РѕС‚С‹/РІС‹РІРѕРґС‹ РєРѕРјР°РЅРґ)
6. РўРѕР»СЊРєРѕ РїРѕСЃР»Рµ вњ… QA Stage СЃС‡РёС‚Р°РµС‚СЃСЏ Р·Р°РІРµСЂС€С‘РЅРЅС‹Рј

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

## Dev services startup rules

РџСЂРё Р·Р°РїСѓСЃРєРµ dev-СЃРµСЂРІРµСЂРѕРІ (backend uvicorn, frontend Vite) СЃРѕР±Р»СЋРґР°Р№ СЃР»РµРґСѓСЋС‰РёРµ РїСЂР°РІРёР»Р°:

1. **Р’СЃРµ СЃРµСЂРІРёСЃС‹ РґРѕР»Р¶РЅС‹ Р·Р°РїСѓСЃРєР°С‚СЊСЃСЏ РІ С„РѕРЅРµ, Р±РµР· РІРёРґРёРјС‹С… РѕРєРѕРЅ/РєРѕРЅСЃРѕР»РµР№.**
   - Р”Р»СЏ backend: `Start-Process -WindowStyle Hidden -PassThru -FilePath 'python' -ArgumentList '-m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000' -WorkingDirectory 'backend/'`
   - Р”Р»СЏ frontend: `Start-Process -WindowStyle Hidden -PassThru -FilePath 'cmd.exe' -ArgumentList '/c cd /d \"frontend/\" && npm run dev'`
   - **РќР•Р›Р¬Р—РЇ** РёСЃРїРѕР»СЊР·РѕРІР°С‚СЊ `UseShellExecute = $true` (РѕС‚РєСЂС‹РІР°РµС‚ РЅРѕРІРѕРµ РѕРєРЅРѕ)
   - **РќР•Р›Р¬Р—РЇ** Р·Р°РїСѓСЃРєР°С‚СЊ python/npm РЅР°РїСЂСЏРјСѓСЋ Р±РµР· `-WindowStyle Hidden`

2. **РЎС‚Р°РЅРґР°СЂС‚РЅС‹Рµ СЃРєСЂРёРїС‚С‹ Р·Р°РїСѓСЃРєР° (РґР»СЏ СЂСѓС‡РЅРѕРіРѕ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ):**
   - `start-dev.ps1` вЂ” Р·Р°РїСѓСЃРє РѕР±РѕРёС… СЃРµСЂРІРёСЃРѕРІ (СЃРєСЂС‹С‚С‹Р№ СЂРµР¶РёРј)
   - `stop-dev.ps1` вЂ” РѕСЃС‚Р°РЅРѕРІРєР° РїРѕ PID-С„Р°Р№Р»Р°Рј
   - `start.cmd` вЂ” Р°Р»СЊС‚РµСЂРЅР°С‚РёРІРЅС‹Р№ Р·Р°РїСѓСЃРє С‡РµСЂРµР· cmd
   - `stop.cmd` вЂ” РѕСЃС‚Р°РЅРѕРІРєР° РїРѕ РїРѕСЂС‚Р°Рј

3. **PID-С„Р°Р№Р»С‹:**
   - Backend: `.backend.pid` (РІ РєРѕСЂРЅРµ РїСЂРѕРµРєС‚Р°)
   - Frontend: `.frontend.pid` (РІ РєРѕСЂРЅРµ РїСЂРѕРµРєС‚Р°)
   - РСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ РґР»СЏ РѕСЃС‚Р°РЅРѕРІРєРё СЃРµСЂРІРёСЃРѕРІ

4. **Р›РѕРіРё:** stdout/stderr СЃРµСЂРІРёСЃРѕРІ РЅРµ РїРµСЂРµРЅР°РїСЂР°РІР»СЏСЋС‚СЃСЏ (РёР·-Р·Р° РѕРіСЂР°РЅРёС‡РµРЅРёР№ PowerShell 5.1 СЃ `-WindowStyle Hidden`). РџСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё Р»РѕРіРёСЂРѕРІР°РЅРёСЏ Р·Р°РїСѓСЃРєР°С‚СЊ РІСЂСѓС‡РЅСѓСЋ РІ РІРёРґРёРјРѕРј СЂРµР¶РёРјРµ.

5. **РџРѕСЂС‚С‹:** backend РЅР° 8000, frontend РЅР° 5173. РџРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј РїСЂРѕРІРµСЂСЏС‚СЊ, С‡С‚Рѕ РїРѕСЂС‚С‹ СЃРІРѕР±РѕРґРЅС‹.