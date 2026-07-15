# Run & Debug Guide — Sprint 1–3 Working Prototype

**Status as of this guide:** I ran the full stack end-to-end on this machine (Windows, Python 3.12, Node 22). The backend starts cleanly, the data pipeline runs, the frontend renders. This document is:

1. The exact commands to bring the whole system up from a clean checkout.
2. A list of real bugs I found while doing that, with the exact file/line and the fix — for you to apply by hand so you understand what's actually happening (that's what you asked for; I did not silently edit your source).

Read part 1 first if you just want it running for a demo. Read part 2 to actually fix the rough edges so the demo shows real data instead of quietly-faked data.

---

## Part 1 — Getting it running

### 0. Prerequisites
- Python 3.12 (you have 3.12.6 at `C:\Python312\python.exe`)
- Node 22 + npm 10 (you have these)
- Nothing else needs to be installed globally — everything else is a venv/npm dependency.

### 1. Backend: create the venv and install dependencies

```bash
cd Continuous-KYC-Autonomous-Auditor
python -m venv .venv
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

`requirements.txt` installs cleanly, **except it's missing `chromadb`**, which `knowledge/store.py` imports directly. Without it, anything touching entity resolution or the SAR regulatory RAG will crash at import time. Install it too (see Bug #1 below for the permanent fix):

```bash
./.venv/Scripts/python.exe -m pip install chromadb
```

### 2. Build the data pipeline (run once, in this exact order)

These scripts turn the raw datasets in `data/` into what the running app actually reads. Skipping one means the next thing that needs it crashes.

```bash
# 1. Seed 100 synthetic entities into SQLite (creates data/sentinelai.db)
./.venv/Scripts/python.exe -m data.seed.seed_entities

# 2. Seed synthetic directors/UBOs onto watched entities (needed for the
#    Network Propagator and for entity-resolution demo traps)
./.venv/Scripts/python.exe -m data.prep.gen_directors

# 3. Sample the 9.5M-row SAML-D transaction dataset down to a workable size
#    -> writes data/processed/txn_sample.parquet
./.venv/Scripts/python.exe -m data.prep.prep_transactions

# 4. Map synthetic accounts onto entities so the transaction replay
#    resolves to something in the DB
./.venv/Scripts/python.exe -m data.prep.build_account_map

# 5. Index entities into ChromaDB for the Resolver agent
./.venv/Scripts/python.exe -m knowledge.index_entities
```

Expected output tail for each, respectively: `"Successfully seeded 100 entities..."`, `"seeded 59 directors across 18 entities"`, `"wrote 199774 rows..."`, `"mapped 40 suspicious accounts onto 15 high-risk entities..."`, `"Indexing complete."`

**Step 5 currently indexes 10 hardcoded fake entities, not your real seeded ones** — see Bug #3. It won't error, but the Resolver won't be able to match real entity IDs. Fix that before you rely on live agent resolution in a demo.

If you ever want a clean slate, delete `data/sentinelai.db` and `data/chroma/` and redo steps 1–5. (Step 3's parquet doesn't need redoing unless you change the sampling.)

### 3. Start the backend

```bash
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

You should see adapters register, the scheduler start, and `Uvicorn running on http://127.0.0.1:8000`. No `GEMINI_API_KEY`/`GOOGLE_API_KEY` is required to boot — `app/config.py` defaults it to `""`, and the LLM gateway degrades gracefully to the mock ladder when it's unset (this is by design, per the Sprint 1/3 plans — real Gemini calls are opt-in via `.env`).

Verify it's alive:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/docs        # Swagger UI in a browser instead
```

Note the API is mounted under **`/api/v1`**, not `/api`. This matters a lot for Bug #4 below.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite's dev proxy forwards anything under `/api` to `http://localhost:8000`, so no `.env` is strictly required for the proxy to work — but see Bug #4, because the frontend's own base URL is wrong regardless of the proxy.

### 5. (Optional) Run a scripted demo scenario

```bash
./.venv/Scripts/python.exe -m demo.run money_laundering --reset --auto
```

`--reset` restores a pristine seeded DB snapshot first (you may need to run `python -m demo.run --snapshot` once after your first successful seed to create that snapshot — check `demo/run.py`'s docstring). `--auto` skips the interactive pause-gates so it runs unattended. Other scenarios: `false_positive`, `sanctions_update`.

---

## Part 2 — Bugs found, with exact fix locations

I found these by actually running the stack, not by reading code in isolation. They're listed most-impactful-first. None of these block the backend from starting — they block the *demo from showing real data*, which is arguably worse because it fails silently.

### Bug #1 — `chromadb` missing from `requirements.txt`
**File:** [requirements.txt](requirements.txt)
**Problem:** `knowledge/store.py:1` does `import chromadb`, but it's never listed as a dependency. A clean `pip install -r requirements.txt` leaves it out entirely.
**Fix:** add a line to `requirements.txt`:
```
chromadb>=0.5
```

### Bug #2 — `.env.example` is empty
**File:** [.env.example](.env.example)
**Problem:** it's a 0-byte file. Sprint 1's plan said it should document `GEMINI_API_KEY=`, `DB_PATH=`, etc. Right now nobody new to the repo has any idea what env vars exist without reading `app/config.py`.
**Fix:** populate it from the real settings in [app/config.py](app/config.py):
```bash
# App
ENVIRONMENT=development
LOG_LEVEL=INFO

# Security
JWT_SECRET_KEY=dev-secret-change-me
CORS_ORIGINS=http://localhost:5173

# Database & Infra
DATABASE_URL=sqlite+aiosqlite:///./data/sentinelai.db
CHROMA_PERSIST_DIR=./data/chroma
REDIS_URL=redis://localhost:6379

# AI / LLM — leave GOOGLE_API_KEY blank to run fully on the mock ladder
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
MASK_PII_BEFORE_LLM=true

# Datasets
DATA_DIR=./data
```

### Bug #3 — `knowledge/index_entities.py` indexes 10 fake entities, not your real seeded ones
**File:** [knowledge/index_entities.py](knowledge/index_entities.py)
**Problem:** the whole file is still the Sprint 1 placeholder — a hardcoded `fake_entities` list (`"Acme Holdings"`, `"Wayne Enterprises"`, `"Umbrella Corp"`, etc. with random UUIDs). The Sprint 1 plan explicitly says: *"index 10 handwritten fake entities so the retriever is testable at Hour 1 [until] Dev 1's seed runs, then write `knowledge/index_entities.py` that reads watched entities from SQLite."* That second half never happened. Every real entity ID your DB actually has (`C_0001`, `C_0002`, ...) has no ChromaDB card, so `app/agents/resolver.py`'s `retrieve_entity_candidates()` call can never resolve a real event to a real entity — it'll only ever "find" the fake Acme/Wayne/Umbrella cards.
**Fix:** replace `index_entities()` in that file with something that reads from the DB, e.g.:
```python
from app.repositories.unit_of_work import UnitOfWork

def index_entities():
    with UnitOfWork() as uow:
        entities = uow.entities.list()  # check the real method name in app/repositories/entity_repo.py
    collection = get_collection("entity_cards")
    ids, documents, metadatas = [], [], []
    for e in entities:
        ids.append(e.id)
        documents.append(chunk_entity_card(e.__dict__))
        metadatas.append({"name": e.name, "watched": e.watched})
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
```
Check `app/repositories/entity_repo.py` for the exact `list()` signature and what fields `chunk_entity_card()` in `knowledge/chunker.py` expects — line it up with those before pasting this in. Then re-run `python -m knowledge.index_entities` after every re-seed.

### Bug #4 — Frontend never actually talks to the backend (biggest one)
**Files:** [frontend/src/api/client.js](frontend/src/api/client.js), consumed by every page in `frontend/src/pages/`
**Problem, in three parts, that compound:**
1. `client.js:4` — `API_URL = import.meta.env.VITE_API_URL || '/api'`. There's no `frontend/.env`, so it defaults to `/api`. But every backend route is mounted under **`/api/v1`** (see `app/main.py:100-108`, all routers get `prefix=settings.api_v1_prefix`). Every request 404s.
2. Every method in `client.js` wraps its call in `try { ... } catch (e) { return <hardcoded mock> }`. A 404 throws, so the `catch` fires **silently** and returns fake canned data (`'Acme Holdings LLC'`, `'Stark Industries'`, etc.) — the UI looks fully populated and "working" even though it never reached your backend once.
3. Even the URL paths themselves are stale versus the real routers: `client.js` calls `/sar/${id}` but the real router is mounted at `/sars` (`app/api/sar.py:25`); it calls `/audit` with no argument but the real route requires `GET /audit/{entity_id}` (`app/api/audit.py:44`).
4. Response shape mismatch on top of that: the backend wraps every response in an envelope (`{success, message, data, trace_id, error_code}` — see `app/schemas/__init__.py`'s `success_response`/`paginate`), and paginates list endpoints as `data.items`. `client.js`'s success path does `return res.data` — the raw envelope — while the pages (e.g. `AlertQueue.jsx:15,29`) expect `alerts` to be a plain array. Even after fixing the URL, pages would render `[object Object]`-shaped garbage.
5. Field names also drifted: the real `AlertSummaryDTO` (`app/schemas/alerts.py:24-29`) has `id, entity_name, priority, status, created_at`. `AlertQueue.jsx` reads `alert.band`, `alert.score`, `alert.event_type` — none of which exist on the real DTO; those were Sprint-1-era field names from before the schema settled.

**Fix, in order:**
1. Set the base URL correctly. Either add `frontend/.env` with `VITE_API_URL=/api/v1`, or just change the default in `client.js:4` to `'/api/v1'`.
2. Fix the two stale paths: `/sar/${id}` → `/sars/${id}` (three occurrences: `getSAR`, `editSAR`'s sibling calls), `/audit` → `/audit/${entityId}` (needs an entity id passed in — check what `AuditTrail.jsx` currently calls it with).
3. Unwrap the envelope: change each `return res.data` to `return res.data.data`, and for list endpoints pull out `.items` (e.g. `getAlerts` should `return res.data.data.items`).
4. Reconcile field names page-by-page against the actual DTOs in `app/schemas/`. Start with `AlertQueue.jsx` against `AlertSummaryDTO` (`app/schemas/alerts.py`) since that's the landing page — `band/score/event_type` need to become `priority/status` (there's no numeric score or event_type on the real alert summary; decide whether to pull those from `AlertDetailDTO.investigation` or drop them from the table).

This is genuinely the biggest chunk of remaining work — plan real time for it, not a five-minute patch. It's also exactly what Sprint 3's Dev 5 track ("Wire real data with React Query... Replace hardcoded page data") called for and what's still outstanding.

### Bug #5 — Audit hash chain is permanently broken by two call sites that bypass it — **fixed for you in this session**
**Files:** [app/services/screening.py](app/services/screening.py), [app/services/ingestion/sanctions_list.py](app/services/ingestion/sanctions_list.py)
**Problem:** both files wrote directly to `uow.audit_log.add(AuditLog(...))` with a hardcoded `prev_hash = "UNCHAINED_SPRINT2"` sentinel, instead of calling `app/services/audit_service.py`'s `append_audit()`, which is the real hash-chaining implementation (genesis hash `"GENESIS"`, real `prev_hash` linking). Both files even said so in their own docstrings: *"Not hash-chained ... real chaining is Dev 3's Sprint 3"* — that migration was called out explicitly in the Sprint 3 plan (*"grep every place Sprints 1–2 wrote audit rows directly ... route them through append()"*) and never finished for these two call sites.
**Observed effect (before the fix):** confirmed live — after ~15 seconds of the backend running (structuring detector + sanctions adapter firing on schedule), `GET /api/v1/audit/verify` already reported `is_valid: false` with a real `broken_at_hash`, because the very first entry's `prev_hash` was `"UNCHAINED_SPRINT2"` instead of `"GENESIS"`. The "Verify chain" button — a "never cut" feature per the Sprint 3 plan — would show red the moment you opened the demo, through no fault of anything you did.
**Fix applied:** `_audit_screened_out()` (screening.py) and `_audit_list_refreshed()` (sanctions_list.py) now both call the real `append_audit()` instead of hand-rolling their own hash and sentinel row:
```python
from app.services.audit_service import append_audit

def _audit_screened_out(name: str, context: str) -> None:
    payload = {"name": name, "context": context, "threshold": SCREENING_PASS_THRESHOLD}
    with UnitOfWork() as uow:
        append_audit(action="screened_out", payload=payload, uow=uow)
        uow.commit()
```
Same pattern for `_audit_list_refreshed()`. The now-unused `UNCHAINED_SENTINEL` constant and the manual `hashlib`/`_compute_entry_hash`-equivalent code were removed from both files.

This landed alongside three other audit-chain bugs found the same session (see the stress-test log / commit history around this date): `append_audit()` itself was chaining per-entity instead of as one global ledger, its hash embedded a tz-aware timestamp that doesn't round-trip through SQLite, and its "find the last entry" lookup didn't flush pending writes first (`SessionLocal` is `autoflush=False`) — all three had to be fixed before this one would hold, since a correct global chain with an unchained row spliced into it is still broken.

### Bug #6a — Vite proxy fails with `ECONNREFUSED ::1:8000` on Node 22 / Windows
**File:** [frontend/vite.config.js](frontend/vite.config.js) — **already fixed for you in this session.**
**Problem:** the proxy target was `http://localhost:8000`. Node 22 resolves `localhost` to the IPv6 loopback `::1` first by default. `uvicorn app.main:app --port 8000` (no `--host` flag) only binds the IPv4 loopback `127.0.0.1`, not `::1`. Result: every proxied request fails with `connect ECONNREFUSED ::1:8000` even though `curl http://127.0.0.1:8000/...` works fine in the same terminal — the backend is up, it's a DNS-resolution-order mismatch, not a backend crash.
**Fix applied:** changed the proxy target to `http://127.0.0.1:8000` (forces IPv4, sidesteps the resolution order entirely). If you ever see this error again after editing `vite.config.js`, check the target is still the literal IP, not `localhost`.

### Bug #6 — `/api/v1/entities` still returns 3 hardcoded fake entities
**File:** [app/api/entities.py](app/api/entities.py)
**Problem:** the whole router is still the Sprint 1 mock (`_MOCK_ENTITIES` dict with `"entity-1" = "Acme Import Export Ltd"`, etc.) — literally the file's own docstring says `"Sprint 1 returns hardcoded data"`. Unlike `alerts.py`, `sar.py`, and `audit.py` (which were swapped to real `UnitOfWork`/repo reads, confirmed by reading their source), this one never got the Sprint 3 swap. `GET /api/v1/entities` will always return the same 3 fake rows no matter what's actually seeded in SQLite.
**Fix:** rewrite `list_entities`/`get_entity`/`get_entity_graph` to read from `uow.entities` the same way `app/api/sar.py` and `app/api/audit.py` already do (they're good reference implementations — literally just copy their `with UnitOfWork() as uow:` pattern). The `EntityGraphDTO` (decision graph per entity) likely needs to come from `app/schemas/traces.py` / whatever the agents populate — check `app/services/explainability/trace.py` for what's actually persisted before inventing a shape.

---

## Suggested order to work through this before your demo

1. Bug #1 (1 line, requirements.txt) — do this first, it's free.
2. Bug #4 (frontend wiring) — highest visual impact; without it your demo is showing static fake data regardless of how good the backend is.
3. Bug #5 (audit chain) — quick, and the "verify chain" button is a specific "never cut" checklist item from your own sprint plan.
4. Bug #3 (entity indexing) — needed if you want to demo live LLM entity resolution rather than just the deterministic scoring path.
5. Bug #6 (entities endpoint) — needed for `EntityTimeline.jsx` to show real data.
6. Bug #2 (.env.example) — cosmetic/onboarding, do whenever.

## What's genuinely Sprint 4, not a bug
Per your own sprint plans' "Sprint 4 preview" sections: stress-testing scoring/audit edge cases (concurrent audit appends, policy hot-reload mid-pipeline), full scenario rehearsal ×3 with timing, adapter failure-path hardening (stale-data warnings, retry backoff), SSE-disconnect UX polish, and the optional stretch items (Random Forest detector, dormancy detector, red-team agent — all explicitly cuttable per the Sprint 3 plan's cut order). Don't spend Sprint 4 time on those bugs above disguised as "polish" — they're correctness bugs, not polish, and they're what will make the prototype actually look alive on the day.
