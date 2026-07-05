# Known Issues & Lessons

## 1. Frontend Encoding (Mojibake)

**Problem:** Russian text in `.tsx`/`.ts` files gets corrupted when saved through certain tools.
The UTF-8 bytes of Cyrillic characters get interpreted as Windows-1251 then saved as UTF-8 again,
producing mojibake: `Р—Р°РіСЂСѓР·РёС‚Рµ` instead of `Загрузите`.

**Detection:** Search for `Р—Р°` in changed files before commit.
Check: `rg 'Р—Р°|РЎРёСЃС‚РµРјР°|С„Р°Р№Р»' frontend/src/`

**Fix:**
```powershell
$bytes = [System.IO.File]::ReadAllBytes($path)
$win1251 = [System.Text.Encoding]::GetEncoding(1251).GetString($bytes)
[System.IO.File]::WriteAllText($path, $win1251, [System.Text.Encoding]::UTF8)
```

**Prevention:** Always save `.tsx`/`.ts` files as UTF-8 with BOM.
Run `rg '[^\x00-\x7F]' frontend/src/ --include '*.tsx' --include '*.ts'` after edits.

## 2. DB Schema Changes with SQLite

**Problem:** `Base.metadata.create_all()` with SQLite does NOT add new columns to existing tables.
New fields added to models after the DB was created are silently missing.

**Fix:** Add explicit ALTER TABLE in `database.py:_run_migrations()` for each new column.

**Prevention:** When adding a field to a model, always add corresponding migration logic.

## 3. Route Collision (GET /api/documents/{id})

**Problem:** Two routers with overlapping paths (`/api/documents/`) caused one to shadow the other.

**Fix:** Changed analysis endpoints to `/api/analyses/` prefix.

**Prevention:** Check for existing routes before adding new ones. Use unique prefixes.

## 4. BackgroundTasks with Async Functions

**Problem:** `BackgroundTasks.add_task()` with an `async def` function creates a coroutine
that never executes because BackgroundTasks doesn't await async functions.

**Fix:** Use `asyncio.create_task()` instead, with self-managed DB sessions.

**Prevention:** Never pass `async def` to `BackgroundTasks.add_task()`.
