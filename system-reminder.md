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
- Before reporting a task as done, verify it without user involvement: typecheck, build, tests, and manual logic trace. Never make the user find defects that could have been caught by running the tools already available in the project.
- Provide a concise final report.

## рџ”ґ Testing discipline (СЃС‚СЂРѕР¶Р°Р№С€Рµ)

- РќРРљРћР“Р”Рђ РЅРµ СѓС‚РІРµСЂР¶РґР°Р№ С‡С‚Рѕ С‚РµСЃС‚ РїСЂРѕС€С‘Р», РµСЃР»Рё С‚С‹ РµРіРѕ РЅРµ Р·Р°РїСѓСЃРєР°Р».
- РќРРљРћР“Р”Рђ РЅРµ СѓС‚РІРµСЂР¶РґР°Р№ С‡С‚Рѕ СЃРµСЂРІРµСЂ РѕС‚РІРµС‡Р°РµС‚, РµСЃР»Рё С‚С‹ РЅРµ СЃРґРµР»Р°Р» curl.
- РќРРљРћР“Р”Рђ РЅРµ СѓС‚РІРµСЂР¶РґР°Р№ С‡С‚Рѕ С„Р°Р№Р» СЃСѓС‰РµСЃС‚РІСѓРµС‚, РµСЃР»Рё С‚С‹ РЅРµ РїСЂРѕРІРµСЂРёР» ls/dir.
- РќРРљРћР“Р”Рђ РЅРµ РіРѕРІРѕСЂРё В«РµСЃР»Рё Р·Р°РїСѓСЃС‚РёС‚СЊ, С‚Рѕ Р±СѓРґРµС‚ СЂР°Р±РѕС‚Р°С‚СЊВ». Р›РёР±Рѕ Р·Р°РїСѓСЃС‚РёР» Рё РїРѕРєР°Р·Р°Р», Р»РёР±Рѕ РЅРµ СѓС‚РІРµСЂР¶РґР°Р№.
- РљРђР–Р”Р«Р™ РѕС‚С‡С‘С‚ Рѕ РІС‹РїРѕР»РЅРµРЅРЅРѕР№ СЂР°Р±РѕС‚Рµ РґРѕР»Р¶РµРЅ СЃРѕРґРµСЂР¶Р°С‚СЊ СЂРµР°Р»СЊРЅС‹Рµ РІС‹РІРѕРґС‹ РєРѕРјР°РЅРґ.
- РџРѕСЃР»Рµ РєР°Р¶РґРѕР№ СЂРµР°Р»РёР·Р°С†РёРё вЂ” РІС‹Р·С‹РІР°Р№ QA-Р°РіРµРЅС‚Р° РЅР° РІРµСЂРёС„РёРєР°С†РёСЋ.
- QA-Р°РіРµРЅС‚ РЅРµ РёРјРµРµС‚ РїСЂР°РІР° РІРµСЂРёС‚СЊ РЅР° СЃР»РѕРІРѕ вЂ” С‚РѕР»СЊРєРѕ СЂРµР°Р»СЊРЅС‹Рµ РєРѕРјР°РЅРґС‹.

## Dev services startup

РџСЂРё Р·Р°РїСѓСЃРєРµ dev-СЃРµСЂРІРµСЂРѕРІ (backend uvicorn, frontend Vite):
- Р’СЃРµ СЃРµСЂРІРёСЃС‹ Р·Р°РїСѓСЃРєР°СЋС‚СЃСЏ РўРћР›Р¬РљРћ РІ СЃРєСЂС‹С‚РѕРј СЂРµР¶РёРјРµ (Р±РµР· РѕРєРѕРЅ/РєРѕРЅСЃРѕР»РµР№)
- РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ: `Start-Process -WindowStyle Hidden -PassThru`
- Р”Р»СЏ frontend (npm.cmd вЂ” batch-С„Р°Р№Р»): Р·Р°РїСѓСЃРєР°С‚СЊ С‡РµСЂРµР· `cmd.exe /c`
- РџРѕСЃР»Рµ Р·Р°РїСѓСЃРєР° РїСЂРѕРІРµСЂСЏС‚СЊ С‡С‚Рѕ СЃРµСЂРІРёСЃС‹ РѕС‚РІРµС‡Р°СЋС‚ (health check / http status)
- PID-С„Р°Р№Р»С‹: `.backend.pid`, `.frontend.pid` РІ РєРѕСЂРЅРµ РїСЂРѕРµРєС‚Р°