# Setup Guide — Running This Project on a Fresh Clone / New Machine

This is a from-zero checklist: clone the repo on a machine that has never touched this codebase, and end with the backend + frontend running. It assumes nothing is installed except Git.

If you hit something not covered here, or want to know about the deeper logic bugs (frontend showing mock data, broken audit chain, etc.) that exist in the current codebase regardless of which machine you run it on, see [RUN_AND_DEBUG_GUIDE.md](RUN_AND_DEBUG_GUIDE.md) — that document covers what to fix; this one covers how to get from a clone to a running process.

---

## 0. Prerequisites

Install these first if the new machine doesn't have them:

| Tool | Version used to validate this guide | Check with |
|---|---|---|
| Python | 3.12.x | `python --version` |
| Node.js | 22.x (npm 10.x) | `node --version` / `npm --version` |
| Git | any recent | `git --version` |

Python 3.11+ should work; the codebase has some `cpython-311` compiled artifacts checked in alongside `cpython-312` ones (see step 2), so both have been run against it at some point.

---

## 1. Clone the repo

```bash
git clone https://github.com/TECH-M-CODE/Continuous-KYC-Autonomous-Auditor.git
cd Continuous-KYC-Autonomous-Auditor
```

(Use your fork's URL if you're working off a fork/branch instead.)

## 2. Clean out stale tracked data (important, easy to miss)

`.gitignore` correctly excludes `*.db`, `data/chroma/`, and `__pycache__/` — but those files were committed to the repo **before** `.gitignore` was set up to exclude them, so git still tracks whatever version currently sits in the history. A fresh clone will hand you someone else's dev SQLite database and vector index, already populated with test data (possibly in an inconsistent state — audit chain, entity IDs, etc. from whoever last ran it).

Delete them locally so the data-pipeline scripts in step 5 build a clean, consistent dataset from scratch:

```bash
rm -f data/sentinelai.db data/sentinelai.db-shm data/sentinelai.db-wal
rm -rf data/chroma
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

(On Windows PowerShell instead: `Remove-Item data\sentinelai.db, data\chroma -Recurse -Force -ErrorAction SilentlyContinue`)

This only deletes your local working copy — it does not touch git history. If you want new clones to stop inheriting these files permanently, that requires `git rm --cached` on those paths plus a commit; that's a repo-maintenance decision for whoever owns `main`, not something to do casually on a feature branch.

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

`requirements.txt` now includes `chromadb` (it was missing before this was fixed — if you're on an older checkout without that line, run `pip install chromadb` separately, or you'll get `ModuleNotFoundError: No module named 'chromadb'` the moment anything touches `knowledge/store.py`).

## 4. Configure environment variables

```bash
cp .env.example .env
```

The defaults in `.env.example` work out of the box for local dev — SQLite (no separate DB server needed), `GOOGLE_API_KEY` blank (runs entirely on the deterministic mock LLM ladder, no API key or billing required for a demo). Only edit `.env` if you specifically want live Gemini calls (set `GOOGLE_API_KEY`) or you're pointing at a different Redis/DB.

## 5. Build the data pipeline (run once, in this exact order)

Each script depends on the previous one's output. Run from the repo root:

```bash
# 1. Seed 100 synthetic entities -> creates data/sentinelai.db
./.venv/Scripts/python.exe -m data.seed.seed_entities

# 2. Seed synthetic directors/UBOs onto watched entities
./.venv/Scripts/python.exe -m data.prep.gen_directors

# 3. Sample the SAML-D transaction dataset -> data/processed/txn_sample.parquet
./.venv/Scripts/python.exe -m data.prep.prep_transactions

# 4. Map synthetic accounts onto entities
./.venv/Scripts/python.exe -m data.prep.build_account_map

# 5. Index entities into ChromaDB (see known-issues note below)
./.venv/Scripts/python.exe -m knowledge.index_entities
```

Expect roughly:
```
Successfully seeded 100 entities into the database.
Watched entities count: 70
...seeded 59 directors across 18 entities...
...wrote 199774 rows...
...mapped 40 suspicious accounts onto 15 high-risk entities...
Indexing complete.
```

**Known issue:** step 5 currently indexes 10 hardcoded placeholder entities rather than your real seeded ones — it runs without error, but live entity-resolution via the agent pipeline won't match real entity IDs until that's fixed. See RUN_AND_DEBUG_GUIDE.md Bug #3. Not a blocker for getting the servers running.

## 6. Start the backend

```bash
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Confirm it's up:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Browse the interactive API docs at `http://127.0.0.1:8000/api/v1/docs`.

Leave this terminal running; open a second terminal for the frontend.

## 7. Frontend: install and configure

```bash
cd frontend
npm install
```

`vite.config.js`'s dev-server proxy already points `/api` at `http://127.0.0.1:8000` (not `http://localhost:8000`) — this matters specifically on Node 18+, which can resolve `localhost` to the IPv6 loopback `::1` first, while `uvicorn` (no `--host` flag) only binds the IPv4 loopback. If you ever see `connect ECONNREFUSED ::1:8000` in the Vite log, check that this file still says `127.0.0.1` and not `localhost`.

No `frontend/.env` is required to start the dev server — the proxy handles routing without one.

## 8. Start the frontend

```bash
npm run dev
```

Open `http://localhost:5173`.

**Known issue:** the pages will render, but currently show static-looking demo data rather than what you just seeded — the frontend's API client points at the wrong base path and silently falls back to hardcoded mock data on any request failure. The backend and data pipeline above are genuinely working; this is a frontend wiring gap. See RUN_AND_DEBUG_GUIDE.md Bug #4 for the exact fix.

## 9. (Optional) Run a scripted demo scenario

```bash
cd ..   # back to repo root
./.venv/Scripts/python.exe -m demo.run money_laundering --reset --auto
```

`--reset` restores a pristine DB snapshot first. If you haven't created one yet on this machine, check `demo/run.py`'s docstring for the snapshot command (`python -m demo.run --snapshot`) — run it once, right after step 5, while your seeded data is known-good.

---

## Quick troubleshooting reference

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'chromadb'` | Old `requirements.txt` without chromadb, or install skipped | `pip install chromadb` |
| `FileNotFoundError: data/processed/txn_sample.parquet not found` | Step 5.3 (`prep_transactions`) not run yet | Run the data pipeline in order (step 5) — the backend constructs `TransactionReplayAdapter` unconditionally at startup, so this file must exist before `uvicorn` will boot |
| `[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions` on `uvicorn` startup | Another process (often a leftover uvicorn from a previous session) is already bound to that port | Windows: `Get-NetTCPConnection -LocalPort 8000` to find the PID, then `Stop-Process -Id <pid> -Force` |
| Vite proxy: `connect ECONNREFUSED ::1:8000` | `vite.config.js` proxy target is `localhost` and Node resolves it to IPv6, but uvicorn only binds IPv4 | Confirm `vite.config.js` uses `http://127.0.0.1:8000` (already fixed in this repo — if you see this, your checkout predates that fix) |
| Frontend pages show data but it never changes / doesn't match what you seeded | Frontend API client is pointed at the wrong base path and is silently using mock fallback data | Known issue — see RUN_AND_DEBUG_GUIDE.md Bug #4 |
| `GET /api/v1/audit/verify` returns `is_valid: false` immediately after a clean seed | Two ingestion call sites bypass the real hash-chaining service | Known issue — see RUN_AND_DEBUG_GUIDE.md Bug #5 |
| Re-running `seed_entities.py` doesn't error on a non-empty DB | It's intentionally idempotent — it deletes existing entity rows before re-adding | Expected behavior, not a bug. Other tables (e.g. `audit_log`) are *not* cleared by any script — for a truly clean slate, delete `data/sentinelai.db` first (step 2) |

---

## Summary checklist

- [ ] Python 3.12 + Node 22 installed
- [ ] Repo cloned
- [ ] Stale tracked `data/sentinelai.db` / `data/chroma/` deleted
- [ ] `.venv` created, `pip install -r requirements.txt` run (chromadb included)
- [ ] `.env` copied from `.env.example`
- [ ] Data pipeline run in order (5 commands)
- [ ] Backend running on `:8000`, `/api/v1/health` returns 200
- [ ] `npm install` run in `frontend/`
- [ ] Frontend running on `:5173`, loads in browser
- [ ] (Optional) demo scenario runs via `demo.run`
