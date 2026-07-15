# Setup Guide — Running This Project on a Fresh Clone / New Machine

This is a from-zero checklist: clone the repo on a machine that has never touched this codebase, and end with the backend + frontend running and showing **real seeded data** end-to-end. It assumes nothing is installed except Git.

The correctness bugs the older version of this guide warned about (frontend showing mock data, broken audit chain, placeholder entity index, empty sanctions cache) have since been **fixed** — see the "What changed" note at the bottom and [RUN_AND_DEBUG_GUIDE.md](RUN_AND_DEBUG_GUIDE.md) for the history. This document is now a clean happy-path setup.

---

## 0. Prerequisites

Install these first if the new machine doesn't have them:

| Tool | Version used to validate this guide | Check with |
|---|---|---|
| Python | 3.12.x | `python --version` |
| Node.js | 22.x (npm 10.x) | `node --version` / `npm --version` |
| Git | any recent | `git --version` |

Python 3.11+ should work; the codebase has some `cpython-311` compiled artifacts checked in alongside `cpython-312` ones, so both have been run against it at some point.

---

## 1. Clone the repo

```bash
git clone https://github.com/TECH-M-CODE/Continuous-KYC-Autonomous-Auditor.git
cd Continuous-KYC-Autonomous-Auditor
```

(Use your fork's URL if you're working off a fork/branch instead.)

## 2. Clean out stale tracked data (important, easy to miss)

`.gitignore` correctly excludes `*.db`, `data/chroma/`, and `__pycache__/` — but those files were committed **before** `.gitignore` excluded them, so a fresh clone hands you someone else's dev SQLite database and vector index, possibly in an inconsistent state.

Delete them locally so the data-pipeline scripts in step 5 build a clean, consistent dataset from scratch:

```bash
rm -f data/sentinelai.db data/sentinelai.db-shm data/sentinelai.db-wal
rm -rf data/chroma
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

(On Windows PowerShell instead: `Remove-Item data\sentinelai.db, data\chroma -Recurse -Force -ErrorAction SilentlyContinue`)

This only deletes your local working copy — it does not touch git history.

## 3. Backend: virtual environment + dependencies

```bash
python -m venv .venv
```

Activate it:
- **Windows (PowerShell):** `./.venv/Scripts/Activate.ps1` (or just call `.venv/Scripts/python.exe` directly without activating, as this guide does below)
- **macOS/Linux:** `source .venv/bin/activate`

Install dependencies:

```bash
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

`requirements.txt` includes `chromadb` and `google-generativeai`. (If you install `pytest` to run the test suite, add `pytest pytest-asyncio` — they aren't runtime dependencies.)

## 4. Configure environment variables

```bash
cp .env.example .env
```

The defaults work out of the box for local dev — SQLite (no separate DB server), and `GOOGLE_API_KEY` blank so all LLM calls run on the deterministic **mock LLM ladder** (no key or billing needed for a demo).

**To use live Gemini instead:** set `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) in `.env`. The factory in `app/infrastructure/gemini_client.py` automatically switches from the mock to the real `GeminiClient` when a key is present — no code change needed. Everything below works identically with or without a key.

## 5. Build the data pipeline (run once, in this exact order)

Each script depends on the previous one's output. Run from the repo root:

```bash
# 1. Seed 100 synthetic entities -> creates data/sentinelai.db
./.venv/Scripts/python.exe -m data.seed.seed_entities

# 2. Seed synthetic directors/UBOs onto watched entities
#    (needed for the Network Propagator AND for guaranteed sanctions hits in the demo)
./.venv/Scripts/python.exe -m data.prep.gen_directors

# 3. Sample the SAML-D transaction dataset -> data/processed/txn_sample.parquet
./.venv/Scripts/python.exe -m data.prep.prep_transactions

# 4. Map synthetic accounts onto entities
./.venv/Scripts/python.exe -m data.prep.build_account_map

# 5. Index the REAL seeded entities into ChromaDB for the Resolver agent
./.venv/Scripts/python.exe -m knowledge.index_entities
```

Expect roughly:
```
Successfully seeded 100 entities into the database.
...seeded 59 directors across 18 entities...
...wrote 199774 rows...
...mapped 40 suspicious accounts onto 15 high-risk entities...
Indexing 100 real entities into ChromaDB...
Indexing complete. 100 entity cards upserted.
```

Notes:
- **Step 5 now indexes your real seeded entities** (`C_0001`, `C_0002`, …) and purges any stale placeholder cards, so live agent entity-resolution matches real IDs.
- **You do not need to seed the sanctions list manually.** The `SanctionsListAdapter` runs immediately on backend startup (step 6) and loads OFAC + OpenSanctions from `data/sanctions/` into `sanctions_cache` (~23k records) within a few seconds. This is what the screening stage matches against, so the first alerts appear shortly after boot.

## 6. Start the backend

```bash
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

On startup you'll see the ingest adapters register and fire, the sanctions cache populate, Loop B (the agent pipeline) start, and **Loop D** (the self-assessment job: red-team drill + dormancy sweep) scheduled ~20s after boot.

Confirm it's up:

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/audit/verify     # should report is_valid: true
```

Browse the interactive API docs at `http://127.0.0.1:8000/api/v1/docs`.

Leave this terminal running; open a second terminal for the frontend.

## 7. Frontend: install and configure

```bash
cd frontend
npm install
```

`vite.config.js`'s dev-server proxy points `/api` at `http://127.0.0.1:8000` (the literal IPv4, **not** `localhost`) — this matters on Node 18+, which can resolve `localhost` to the IPv6 loopback `::1` first, while `uvicorn` (no `--host` flag) binds only IPv4. If you ever see `connect ECONNREFUSED ::1:8000` in the Vite log, check this file still says `127.0.0.1`.

The frontend's API base URL defaults to `/api/v1` (in `src/api/client.js`), which the proxy forwards to the backend. No `frontend/.env` is required.

## 8. Start the frontend

```bash
npm run dev
```

Open the URL Vite prints — usually `http://localhost:5173`, or `http://localhost:5174` if 5173 is taken. (Both ports are in the backend's CORS allow-list.)

The pages now render **real data from your seeded database**: the entity list, alert queue, SAR review, audit trail (with a working "Verify chain" badge), and the Admin page's Red-Team Detection Health card (backed by `GET /api/v1/drill/latest`).

## 9. Trigger a live alert (quick smoke test)

Inject an adverse-media event for a watched entity that has a sanctioned director; Loop B picks it up within ~5s and creates an alert:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/inject \
  -H "Content-Type: application/json" \
  -d '{"event_type":"adverse_media","title":"Sanctions probe: Global Mining Solutions 2","text":"Global Mining Solutions 2 linked to sanctioned individual Pierre Cahuzac.","entity_hint":"C_0002"}'
```

Then watch `GET /api/v1/alerts` — the total increments, the new alert appears in the dashboard queue (via SSE), and `GET /api/v1/audit/verify` stays `is_valid: true`.

## 10. (Optional) Run a scripted demo scenario

```bash
cd ..   # back to repo root
./.venv/Scripts/python.exe -m demo.run money_laundering --reset --auto
```

`--reset` restores a pristine DB snapshot first; if you haven't created one yet, see `demo/run.py`'s docstring for `python -m demo.run --snapshot` (run it once, right after step 5, while your seeded data is known-good). Other scenarios: `false_positive`, `sanctions_update`.

## 11. (Optional) Run the test suite

```bash
./.venv/Scripts/python.exe -m pip install pytest pytest-asyncio
./.venv/Scripts/python.exe -m pytest demo/tests -q     # 30 tests
```

---

## Quick troubleshooting reference

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'chromadb'` | Old `requirements.txt`, or install skipped | `pip install chromadb` |
| `FileNotFoundError: data/processed/txn_sample.parquet not found` | Step 5.3 (`prep_transactions`) not run | Run the data pipeline in order — the backend builds `TransactionReplayAdapter` at startup, so this file must exist before `uvicorn` boots |
| `[WinError 10013] ... socket ... forbidden` on `uvicorn` startup | A leftover process is bound to the port | Windows: `Get-NetTCPConnection -LocalPort 8000` to find the PID, then `Stop-Process -Id <pid> -Force` |
| Vite proxy: `connect ECONNREFUSED ::1:8000` | `vite.config.js` target is `localhost`, resolved to IPv6, but uvicorn binds IPv4 | Confirm the target is `http://127.0.0.1:8000` |
| Frontend loads but the alert queue is empty | Screening only produces alerts once `sanctions_cache` is populated | Give the backend a few seconds after boot (the sanctions adapter runs on startup), or trigger one manually with step 9 |
| `GET /api/v1/audit/verify` returns `is_valid: false` | A write bypassed the hash-chain service | Should not happen on a clean seed; if it does, re-check you're on a current checkout (the two historical bypass sites were fixed) |
| Re-running `seed_entities.py` on a non-empty DB doesn't error | It's intentionally idempotent (deletes entity rows before re-adding) | Expected. Other tables (e.g. `audit_log`) aren't cleared by any script — for a truly clean slate, delete `data/sentinelai.db` first (step 2) |

---

## What changed vs. the older guide

The following were open "known issues" in earlier revisions and are now fixed in the code:

- **Real entity indexing** — `knowledge/index_entities.py` indexes the seeded DB entities (not 10 placeholders) and purges stale cards.
- **Frontend wiring** — `src/api/client.js` uses the correct `/api/v1` base, unwraps the response envelope, uses the real route paths, and no longer silently falls back to mock data.
- **Audit hash chain** — the two ingestion call sites that bypassed the chain now route through `append_audit()`; `/audit/verify` stays valid.
- **Sanctions cache populated on boot** — a missing `import hashlib` had been crashing the sanctions adapter, leaving `sanctions_cache` empty and starving the whole pipeline; fixed, so screening produces real alerts.
- **No reprocessing storms** — `run_pipeline` now marks every non-error event processed, so Loop B doesn't re-draw the same events and flood duplicate alerts.
- **New endpoints/loops** — `GET /api/v1/drill/latest` (detection health), `GET /api/v1/entities/{id}/graph` (decision graph), and **Loop D** (scheduled red-team drill + dormancy sweep).

---

## Summary checklist

- [ ] Python 3.12 + Node 22 installed
- [ ] Repo cloned
- [ ] Stale tracked `data/sentinelai.db` / `data/chroma/` deleted
- [ ] `.venv` created, `pip install -r requirements.txt` run
- [ ] `.env` copied from `.env.example` (optionally set `GOOGLE_API_KEY` for live Gemini)
- [ ] Data pipeline run in order (5 commands)
- [ ] Backend running on `:8000`, `/api/v1/health` returns 200, `/api/v1/audit/verify` is valid
- [ ] `npm install` run in `frontend/`
- [ ] Frontend running on `:5173`/`:5174`, shows real seeded data
- [ ] (Optional) live alert triggered via step 9 / demo scenario runs / tests pass
