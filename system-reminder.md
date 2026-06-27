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

## Dev services startup

При запуске dev-серверов (backend uvicorn, frontend Vite):
- Все сервисы запускаются ТОЛЬКО в скрытом режиме (без окон/консолей)
- Использовать: `Start-Process -WindowStyle Hidden -PassThru`
- Для frontend (npm.cmd — batch-файл): запускать через `cmd.exe /c`
- После запуска проверять что сервисы отвечают (health check / http status)
- PID-файлы: `.backend.pid`, `.frontend.pid` в корне проекта