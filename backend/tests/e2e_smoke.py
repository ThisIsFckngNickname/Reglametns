"""
End-to-end smoke test for SRP.

Runs the full pipeline:
  1. Health check
  2. Authentication (register if needed, login, /me)
  3. Companies CRUD (list, get)
  4. Document upload -> approve (triggers RAG indexing) -> verify
  5. Document generation with context
  6. User profile with active company

Run:
    python -m tests.e2e_smoke
    python tests/e2e_smoke.py

Requires the server to be running (default: http://localhost:8000).
Set SRP_BASE_URL env var to override.
"""

import sys
import os
import json
import random
import time
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import httpx

# --- Configuration ---------------------------------------------------
BASE_URL = os.environ.get("SRP_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"

# Try these credentials in order
CREDENTIALS_TO_TRY = [
    {"email": "admin@gmail.com", "password": "admin123"},
    {"email": "admin@gmail.com", "password": "Admin12+"},
    {"email": "admin@gmail.com", "password": "password"},
    {"email": "admin@gmail.com", "password": "admin"},
    {"email": "zhelomsky@gmail.com", "password": "admin123"},
]

# If all credentials fail, register a fresh user
FALLBACK_REGISTER = True

# Pass / Fail counters
passed = 0
failed = 0
skipped = 0
errors = []

_test_user_was_registered = False


def _ok(name: str):
    global passed
    passed += 1
    print(f"  [PASS] {name}")
    sys.stdout.flush()


def _fail(name: str, detail: str):
    global failed
    failed += 1
    errors.append((name, detail))
    print(f"  [FAIL] {name}: {detail}")
    sys.stdout.flush()


def _skip(name: str, reason: str):
    global skipped
    skipped += 1
    print(f"  [SKIP] {name}: {reason}")
    sys.stdout.flush()


# --- Helpers ---------------------------------------------------------
def _r_summary(r: httpx.Response) -> str:
    """Short response summary for error messages."""
    try:
        body = r.json()
        if isinstance(body, dict) and "detail" in body:
            d = body["detail"]
            if isinstance(d, dict):
                return f"HTTP {r.status_code}: {d.get('message', d)}"
            return f"HTTP {r.status_code}: {d}"
        return f"HTTP {r.status_code}: {json.dumps(body, ensure_ascii=False)[:200]}"
    except Exception:
        return f"HTTP {r.status_code}: {r.text[:200]}"


async def _try_login(client: httpx.AsyncClient, email: str, password: str):
    """Try to login with given credentials. Returns True on success."""
    r = await client.post("/auth/login", json={
        "email": email,
        "password": password,
    })
    if r.status_code == 200:
        return r.json()
    return None


async def _register_user(client: httpx.AsyncClient) -> dict:
    """Register a new user and return login result."""
    ts = int(time.time())
    email = f"e2e_test_{ts}@example.com"
    password = "TestPass123!"
    r = await client.post("/auth/register", json={
        "email": email,
        "password": password,
    })
    if r.status_code == 201:
        global _test_user_was_registered
        _test_user_was_registered = True
        result = r.json()
        print(f"     Registered new user: {email}")
        return result
    return None


async def main():
    global passed, failed, skipped, errors, _test_user_was_registered
    passed = failed = skipped = 0
    errors = []
    _test_user_was_registered = False

    print("=" * 70)
    print("  SRP End-to-End Smoke Test")
    print(f"  Target: {BASE_URL}{API_PREFIX}")
    print("=" * 70)
    sys.stdout.flush()

    async with httpx.AsyncClient(base_url=f"{BASE_URL}{API_PREFIX}", timeout=30) as client:
        health_client = httpx.AsyncClient(base_url=BASE_URL, timeout=10)

        # ------------------ 1. Health ------------------
        print("\n--- 1. Server Health ---")
        try:
            r = await health_client.get("/health")
            if r.status_code == 200:
                _ok("GET /health")
                print(f"     -> {r.json()}")
            else:
                _fail("GET /health", _r_summary(r))
        except Exception as e:
            _fail("GET /health", f"Connection failed: {e}")
            print("\n[!] Server unreachable. Aborting.")
            await health_client.aclose()
            return
        finally:
            await health_client.aclose()

        # ------------------ 2. Authentication -----------
        print("\n--- 2. Authentication ---")

        # 2a. Try to login with known credentials, or register
        login_result = None
        for cred in CREDENTIALS_TO_TRY:
            print(f"     Trying login: {cred['email']} / {cred['password']}")
            login_result = await _try_login(client, cred["email"], cred["password"])
            if login_result:
                print(f"     Login successful with {cred['email']}")
                break

        if not login_result and FALLBACK_REGISTER:
            print("     Trying to register a new user...")
            login_result = await _register_user(client)

        if not login_result:
            _fail("Authentication", "All login attempts and registration failed")
            print("\n[!] Authentication failed. Aborting.")
            return

        _ok("Authentication (login/register)")
        token = login_result.get("access_token", "")
        refresh_token = login_result.get("refresh_token", "")
        print(f"     Token type: {login_result.get('token_type')}")
        print(f"     Access token: {token[:40]}...")
        print(f"     Refresh token: {refresh_token[:40]}...")
        print(f"     Expires in: {login_result.get('expires_in')}s")
        client.headers["Authorization"] = f"Bearer {token}"

        # 2b. Get current user (/me)
        user_info = None
        try:
            r = await client.get("/auth/me")
            if r.status_code == 200:
                _ok("GET /auth/me")
                user_info = r.json()
                print(f"     User ID: {user_info.get('id')}")
                print(f"     Email:   {user_info.get('email')}")
                print(f"     Verified: {user_info.get('is_verified')}")
                ac = user_info.get("active_company")
                if ac:
                    print(f"     Active company: {ac.get('id')} -- {ac.get('name')}")
                else:
                    print("     [!] No active company set!")
                companies = user_info.get("companies", [])
                print(f"     Companies: {len(companies)}")
                for c in companies:
                    print(f"       - id={c.get('company_id')} name={c.get('company_name')} role={c.get('role')}")
            else:
                _fail("GET /auth/me", _r_summary(r))
        except Exception as e:
            _fail("GET /auth/me", str(e))

        # Determine if current user is admin (for admin-only tests)
        is_admin = False
        if user_info:
            for c in user_info.get("companies", []):
                if c.get("role") == "admin":
                    is_admin = True
                    break

        # ------------------ 3. Companies ----------------
        print("\n--- 3. Companies ---")

        # 3a. List companies
        companies = []
        try:
            r = await client.get("/companies")
            if r.status_code == 200:
                _ok("GET /companies")
                companies = r.json()
                print(f"     Total companies: {len(companies)}")
                for c in companies:
                    print(f"       [{c['id']}] {c.get('name')} (INN: {c.get('inn')})")
            else:
                _fail("GET /companies", _r_summary(r))
        except Exception as e:
            _fail("GET /companies", str(e))

        # 3b. Get specific company by ID
        if companies:
            cid = companies[0]["id"]
            try:
                r = await client.get(f"/companies/{cid}")
                if r.status_code == 200:
                    _ok(f"GET /companies/{cid}")
                    c = r.json()
                    print(f"     Company: {c.get('name')}")
                    print(f"     Legal form: {c.get('legal_form')}")
                    print(f"     Use GOST: {c.get('use_gost')}")
                else:
                    _fail(f"GET /companies/{cid}", _r_summary(r))
            except Exception as e:
                _fail(f"GET /companies/{cid}", str(e))

        # 3c. Create a new company (admin only)
        if is_admin:
            ts = int(time.time())
            new_company_name = f"E2E Test Company {ts}"
            try:
                r = await client.post("/companies", json={
                    "name": new_company_name,
                    "inn": f"{random.randint(1000000000, 9999999999)}",
                    "legal_form": "ООО",
                    "use_gost": True,
                })
                if r.status_code == 201:
                    _ok("POST /companies (create)")
                    created = r.json()
                    new_company_id = created["id"]
                    print(f"     Created company id={new_company_id}, name={created.get('name')}")

                    # Update it
                    try:
                        r2 = await client.put(f"/companies/{new_company_id}", json={
                            "name": f"{new_company_name} -- updated",
                            "use_gost": False,
                        })
                        if r2.status_code == 200:
                            _ok(f"PUT /companies/{new_company_id} (update)")
                            updated = r2.json()
                            print(f"     Updated name: {updated.get('name')}")
                            print(f"     use_gost: {updated.get('use_gost')}")
                        else:
                            _fail(f"PUT /companies/{new_company_id}", _r_summary(r2))
                    except Exception as e2:
                        _fail(f"PUT /companies/{new_company_id}", str(e2))

                    # Delete it
                    try:
                        r3 = await client.delete(f"/companies/{new_company_id}")
                        if r3.status_code == 200:
                            _ok(f"DELETE /companies/{new_company_id} (cleanup)")
                            print(f"     {r3.json().get('message')}")
                        else:
                            _fail(f"DELETE /companies/{new_company_id}", _r_summary(r3))
                    except Exception as e3:
                        _fail(f"DELETE /companies/{new_company_id}", str(e3))
                elif r.status_code == 409:
                    _skip("POST /companies (create)", "Company already exists")
                else:
                    _fail("POST /companies (create)", _r_summary(r))
            except Exception as e:
                _fail("POST /companies (create)", str(e))
        else:
            _skip("POST /companies (create)", "Admin privileges required")
            _skip("PUT /companies (update)", "Admin privileges required")
            _skip("DELETE /companies (delete)", "Admin privileges required")

        # ------------------ 4. Documents ----------------
        print("\n--- 4. Document Upload & Approve ---")

        # 4a. Upload a document
        doc_path = Path(__file__).parent / "test_data" / "sample.docx"
        if not doc_path.exists():
            doc_path = Path.cwd() / "tests" / "test_data" / "sample.docx"

        uploaded_doc_id = None
        if doc_path.exists():
            try:
                with open(doc_path, "rb") as f:
                    files = {
                        "file": ("sample_e2e.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    }
                    ts = int(time.time())
                    data = {"title": f"E2E Upload Test {ts}"}
                    r = await client.post("/documents/upload", files=files, data=data)
                if r.status_code == 201:
                    _ok("POST /documents/upload")
                    doc = r.json()
                    uploaded_doc_id = doc["id"]
                    print(f"     Document ID: {uploaded_doc_id}")
                    print(f"     Title: {doc.get('title')}")
                    print(f"     Status: {doc.get('status')}")
                    print(f"     File type: {doc.get('file_type')}")
                    print(f"     File size: {doc.get('file_size')}")
                    print(f"     Sections: {doc.get('sections_count')}")
                    print(f"     Tables: {doc.get('tables_count')}")
                    print(f"     Terms: {doc.get('terms_count')}")
                else:
                    _fail("POST /documents/upload", _r_summary(r))
            except Exception as e:
                _fail("POST /documents/upload", str(e))
        else:
            _skip("POST /documents/upload", f"Test file not found: {doc_path}")

        # 4b. Get the uploaded document details
        if uploaded_doc_id:
            try:
                r = await client.get(f"/documents/{uploaded_doc_id}")
                if r.status_code == 200:
                    _ok(f"GET /documents/{uploaded_doc_id}")
                    doc = r.json()
                    print(f"     Title: {doc.get('title')}")
                    print(f"     Status: {doc.get('status')}")
                    print(f"     Company ID: {doc.get('company_id')}")
                    cv = doc.get("current_version")
                    if cv:
                        print(f"     Version: {cv.get('version_number')} ({cv.get('file_type')})")
                    stats = doc.get("stats", {})
                    print(f"     Stats: sections={stats.get('sections_count')}, "
                          f"tables={stats.get('tables_count')}, "
                          f"terms={stats.get('terms_count')}")
                else:
                    _fail(f"GET /documents/{uploaded_doc_id}", _r_summary(r))
            except Exception as e:
                _fail(f"GET /documents/{uploaded_doc_id}", str(e))

        # 4c. Approve the document (triggers RAG indexing + pattern analysis)
        if uploaded_doc_id:
            try:
                r = await client.put(f"/documents/{uploaded_doc_id}", json={
                    "status": "approved"
                })
                if r.status_code == 200:
                    _ok(f"PUT /documents/{uploaded_doc_id} -> approved")
                    doc = r.json()
                    print(f"     New status: {doc.get('status')}")
                    print(f"     RAG indexing and pattern analysis triggered in background")
                else:
                    _fail(f"PUT /documents/{uploaded_doc_id} -> approved", _r_summary(r))
            except Exception as e:
                _fail(f"PUT /documents/{uploaded_doc_id} -> approved", str(e))

        # 4d. List documents
        try:
            r = await client.get("/documents", params={"page": 1, "page_size": 5})
            if r.status_code == 200:
                _ok("GET /documents (paginated)")
                data = r.json()
                items = data.get("items", data)
                if isinstance(items, list):
                    print(f"     Total items in response: {len(items)}")
                total = data.get("total", "N/A")
                page = data.get("page", "N/A")
                print(f"     Pagination: total={total}, page={page}")
            else:
                _fail("GET /documents", _r_summary(r))
        except Exception as e:
            _fail("GET /documents", str(e))

        # 4e. Get document sections (verify parsing worked)
        if uploaded_doc_id:
            try:
                r = await client.get(f"/documents/{uploaded_doc_id}/sections")
                if r.status_code == 200:
                    sections = r.json()
                    _ok(f"GET /documents/{uploaded_doc_id}/sections")
                    print(f"     Sections: {len(sections)}")
                    for s in sections[:5]:
                        print(f"       [lvl={s.get('level')}] {s.get('title')} (order={s.get('order_num')})")
                    if len(sections) > 5:
                        print(f"       ... and {len(sections) - 5} more")
                else:
                    _fail(f"GET /documents/{uploaded_doc_id}/sections", _r_summary(r))
            except Exception as e:
                _fail(f"GET /documents/{uploaded_doc_id}/sections", str(e))

        # 4f. Get document terms
        if uploaded_doc_id:
            try:
                r = await client.get(f"/documents/{uploaded_doc_id}/terms")
                if r.status_code == 200:
                    terms = r.json()
                    _ok(f"GET /documents/{uploaded_doc_id}/terms")
                    print(f"     Terms: {len(terms)}")
                    for t in terms[:3]:
                        print(f"       {t.get('term')} -> {t.get('definition')[:60]}")
                else:
                    _fail(f"GET /documents/{uploaded_doc_id}/terms", _r_summary(r))
            except Exception as e:
                _fail(f"GET /documents/{uploaded_doc_id}/terms", str(e))

        # 4g. Get document abbreviations
        if uploaded_doc_id:
            try:
                r = await client.get(f"/documents/{uploaded_doc_id}/abbreviations")
                if r.status_code == 200:
                    abbrevs = r.json()
                    _ok(f"GET /documents/{uploaded_doc_id}/abbreviations")
                    print(f"     Abbreviations: {len(abbrevs)}")
                    for a in abbrevs[:3]:
                        print(f"       {a.get('abbreviation')} -> {a.get('full_form')}")
                else:
                    _fail(f"GET /documents/{uploaded_doc_id}/abbreviations", _r_summary(r))
            except Exception as e:
                _fail(f"GET /documents/{uploaded_doc_id}/abbreviations", str(e))

        # 4h. Get document tables
        if uploaded_doc_id:
            try:
                r = await client.get(f"/documents/{uploaded_doc_id}/tables")
                if r.status_code == 200:
                    tables = r.json()
                    _ok(f"GET /documents/{uploaded_doc_id}/tables")
                    print(f"     Tables: {len(tables)}")
                    for t in tables[:2]:
                        print(f"       caption={t.get('caption')}, {t.get('rows_count')}x{t.get('cols_count')}")
                else:
                    _fail(f"GET /documents/{uploaded_doc_id}/tables", _r_summary(r))
            except Exception as e:
                _fail(f"GET /documents/{uploaded_doc_id}/tables", str(e))

        # 4i. Download document version
        if uploaded_doc_id:
            try:
                r = await client.get(f"/documents/{uploaded_doc_id}/versions")
                if r.status_code == 200:
                    versions = r.json()
                    _ok(f"GET /documents/{uploaded_doc_id}/versions")
                    print(f"     Versions: {len(versions)}")
                    if versions:
                        v = versions[0]
                        print(f"       v{v.get('version_number')}: {v.get('file_type')}, {v.get('file_size')} bytes")
                        v_id = v.get("id")
                        if v_id:
                            try:
                                r2 = await client.get(f"/documents/versions/{v_id}/download")
                                if r2.status_code == 200:
                                    _ok(f"GET /documents/versions/{v_id}/download")
                                    content_type = r2.headers.get("content-type", "")
                                    content_len = len(r2.content)
                                    print(f"       Downloaded: {content_len} bytes, type={content_type}")
                                else:
                                    _fail(f"GET /documents/versions/{v_id}/download", _r_summary(r2))
                            except Exception as e2:
                                _fail(f"GET /documents/versions/{v_id}/download", str(e2))
                else:
                    _fail(f"GET /documents/{uploaded_doc_id}/versions", _r_summary(r))
            except Exception as e:
                _fail(f"GET /documents/{uploaded_doc_id}/versions", str(e))

        # ------------------ 5. Document Generation ------
        print("\n--- 5. Document Generation ---")

        try:
            # The generator endpoint uses Form data (not JSON)
            # Use a shorter timeout for this call since AI might be unavailable
            r = await client.post("/generator/generate", data={
                "context": (
                    "Sozdajte reglament po ohrane truda dlya ofisnyh rabotnikov. "
                    "Dokument dolzhen soderzhat: obshie polozheniya, trebovaniya bezopasnosti, "
                    "poryadok dejstvij pri chrezvychajnyh situaciyah."
            ),}, timeout=15.0)
            if r.status_code == 200:
                _ok("POST /generator/generate")
                result = r.json()
                print(f"     Document ID: {result.get('id')}")
                print(f"     Title: {result.get('title')}")
                print(f"     Status: {result.get('status')}")
                cv = result.get("current_version")
                if cv:
                    print(f"     Version: v{cv.get('version_number')} ({cv.get('file_type')}, {cv.get('file_size')} bytes)")
                stats = result.get("stats", {})
                print(f"     Stats: sections={stats.get('sections_count')}, tables={stats.get('tables_count')}")
            elif r.status_code == 503:
                _skip("POST /generator/generate", "AI service unavailable (503)")
                print(f"     Response: {r.text[:200]}")
            else:
                _fail("POST /generator/generate", _r_summary(r))
        except httpx.ReadTimeout:
            _skip("POST /generator/generate", "AI service timed out (15s) - expected if no LLM configured")
        except Exception as e:
            _fail("POST /generator/generate", str(e))

        # ------------------ 6. User Profile -------------
        print("\n--- 6. User Profile Verification ---")

        try:
            r = await client.get("/auth/me")
            if r.status_code == 200:
                _ok("GET /auth/me (profile verification)")
                me = r.json()
                ac = me.get("active_company")
                if ac:
                    print(f"     Active company: id={ac.get('id')}, name={ac.get('name')}")
                else:
                    print("     [!] No active company!")
                comps = me.get("companies", [])
                print(f"     User belongs to {len(comps)} company/ies")
                if comps:
                    for c in comps:
                        print(f"       [{c.get('company_id')}] {c.get('company_name')} -- {c.get('role')}")
            else:
                _fail("GET /auth/me (profile verification)", _r_summary(r))
        except Exception as e:
            _fail("GET /auth/me (profile verification)", str(e))

    # --- Summary ------------------------------------------------
    print("\n" + "=" * 70)
    total = passed + failed + skipped
    print(f"  RESULTS:  [PASS] {passed}   [FAIL] {failed}   [SKIP] {skipped}   [TOTAL: {total}]")
    if _test_user_was_registered:
        print("  NOTE: A test user was registered during this run.")
    if errors:
        print("\n  FAILURES:")
        for name, detail in errors:
            print(f"    [FAIL] {name}")
            print(f"       {detail}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
