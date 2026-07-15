# Sprint 1 — Foundation (Day 1, Morning ≈ 4 hours)

**Project:** Continuous KYC Autonomous Auditor (CXKYC) — Tech Mahindra CODE Hackathon, Challenge 3

**Sprint goal:** By end of sprint, `uvicorn app.main:app` starts cleanly, `/health` returns green, the SQLite database is created with all 9 tables, every dashboard page loads with fake-but-correctly-shaped data, and the frontend receives a dummy SSE event live. Nothing is "real" yet — everything is mocks behind frozen interfaces. Sprint 2 swaps mocks for real logic without changing any contract.

**Decision made for this plan:** Frontend = **React + Vite + Tailwind + React Router** (React Flow, Axios, React Query added in Sprint 2). SSE via native `EventSource` regardless — it works identically in React.

---

## 0. Repository Structure (create in first 15 minutes — one person commits this, everyone pulls)

```
cxkyc/
├── README.md
├── requirements.txt
├── policy.yaml                      # risk weights & thresholds (Dev 1 stubs it)
├── .env.example                     # GEMINI_API_KEY=, DB_PATH=, etc.
│
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + lifespan (Dev 4)
│   ├── config.py                    # pydantic-settings (Dev 4)
│   │
│   ├── schemas/                     # ★ SHARED CONTRACTS — Pydantic models
│   │   ├── __init__.py              #   (Dev 1 + Dev 4 co-own, FROZEN by Hour 1.5)
│   │   ├── events.py                # RawEvent
│   │   ├── entities.py              # EntityProfile, EntityPerson
│   │   ├── alerts.py                # Alert (score, band, evidence[])
│   │   ├── sar.py                   # SARDraft (narrative, citations, status, version)
│   │   └── audit.py                 # AuditEntry (actor, action, hash, prev_hash)
│   │
│   ├── models/                      # SQLAlchemy ORM tables (Dev 1)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── events.py                # events_raw
│   │   ├── entities.py              # entities, entity_persons, account_entity_map
│   │   ├── risk.py                  # risk_events, alerts
│   │   ├── sar.py                   # sar_draft
│   │   ├── audit.py                 # audit_log
│   │   └── sanctions.py             # sanctions_cache
│   │
│   ├── repositories/                # Data access layer (Dev 1)
│   │   ├── __init__.py
│   │   ├── unit_of_work.py
│   │   ├── event_repo.py
│   │   ├── entity_repo.py
│   │   ├── alert_repo.py
│   │   ├── sar_repo.py
│   │   ├── audit_repo.py
│   │   └── sanctions_repo.py
│   │
│   ├── infrastructure/              # Cross-cutting infra (Dev 2)
│   │   ├── __init__.py
│   │   ├── broker.py                # AsyncioBroker (pub/sub)
│   │   ├── cache.py                 # LocalMemoryCache (TTL)
│   │   ├── llm_gateway.py           # retry → fallback → cache → degrade
│   │   └── llm_mock.py              # canned Gemini JSON responses
│   │
│   ├── api/                         # HTTP layer (Dev 4)
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── health.py                # /health
│   │   ├── alerts.py                # /api/alerts (hardcoded JSON)
│   │   ├── entities.py              # /api/entities/{id} (hardcoded)
│   │   ├── sar.py                   # /api/sar (hardcoded)
│   │   ├── audit.py                 # /api/audit (hardcoded)
│   │   ├── watchlist.py             # /api/watchlist (hardcoded)
│   │   └── sse.py                   # /api/stream — dummy alert.new every 10s
│   │
│   └── services/                    # EMPTY stubs — filled in Sprint 2
│       ├── __init__.py
│       └── scoring/__init__.py
│
├── knowledge/                       # Vector store layer (Dev 3)
│   ├── __init__.py
│   ├── store.py                     # ChromaDB client + 3 collections
│   ├── chunker.py
│   ├── embedder.py
│   ├── retriever.py                 # mock retriever (top-3 entity cards)
│   └── prep_regulatory.py           # GDPR/PrivacyQA chunking prep
│
├── data/
│   ├── raw/                         # git-ignored: KYC csv, SAML-D, sanctions files
│   ├── processed/                   # txn_sample.parquet etc. (Sprint 2)
│   └── seed/
│       └── seed_entities.py         # KYC profiles → entities (Dev 1)
│
├── demo/                            # Sprint 3 — empty placeholder
│   └── __init__.py
│
├── frontend/                        # Dev 5
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx                  # Router + layout shell
│       ├── api/client.js            # fetch wrapper (Axios in Sprint 3)
│       ├── hooks/useSSE.js          # EventSource hook
│       ├── components/
│       │   ├── Layout.jsx           # sidebar nav + header
│       │   └── StatusBadge.jsx      # score-band color chips
│       └── pages/
│           ├── AlertQueue.jsx
│           ├── EntityTimeline.jsx
│           ├── SARReview.jsx
│           ├── AuditTrail.jsx
│           └── AdminWatchlist.jsx
│
└── tests/
    ├── test_repositories.py         # Dev 1
    ├── test_infrastructure.py       # Dev 2
    └── test_api_shapes.py           # Dev 4
```

---

## 1. The One Shared Task (Hour 0 → 1.5): Freeze the Contracts

Before anyone builds in parallel, **Dev 1 and Dev 4 together write `app/schemas/`** — the Pydantic models everyone codes against. This is a 45–60 min pairing session while Devs 2, 3, 5 do their environment setup. Once merged, schemas are **frozen** — changes after this need whole-team agreement.

Key shapes to lock (from the design doc):

**RawEvent** — `id, source, event_type, content_hash (SHA-256), occurred_at (UTC), raw_text, normalized_names[], payload (JSON), is_drill (bool, default false), processed (bool)`

**Alert** — `id, entity_id, band (medium|high|critical), score, velocity, event_type, evidence[] ({source, snippet, relevance}), status, created_at`

**SARDraft** — `id, alert_id, entity_id, narrative, regulatory_basis[] ({citation, passage}), version, status (pending_review|approved|rejected), created_at`

**AuditEntry** — `id, seq, actor (agent name or human user), action, detail (JSON), entry_hash, prev_hash, created_at`

**EntityProfile** — `id, name, country, sector, sector_risk, pep_flag, sanctions_flag, fatf_country_flag, base_score, current_score, watched (bool)`

---

## 2. Dev 1 — Data Layer (SQLite schema + repositories + UnitOfWork)

**Folders owned:** `app/models/`, `app/repositories/`, `data/seed/`, `policy.yaml` (stub)

**Why first / why critical:** Every other dev codes against this schema from Sprint 2 onward. The schema must be committed and frozen by **Hour 2.5** — later changes cascade into everyone's work.

### Tasks (in order)

1. **`app/models/base.py`** — SQLAlchemy engine factory. Enable WAL mode on connect:
   ```python
   @event.listens_for(engine, "connect")
   def set_wal(dbapi_conn, _):
       dbapi_conn.execute("PRAGMA journal_mode=WAL")
       dbapi_conn.execute("PRAGMA foreign_keys=ON")
   ```
2. **All 9 tables** as ORM models, mirroring the frozen schemas:
   - `events_raw` — with **UNIQUE constraint on `content_hash`** (the dedup guard from activity diagram 5.1) and index on `(processed, occurred_at)`
   - `entities` — index on `name` and `watched`
   - `entity_persons` — `(entity_id, person_name, role)` — the shared-directors graph for the Network Propagator later
   - `account_entity_map` — `(account_no, entity_id)` — the SAML-D linking table (populated Sprint 2, table exists now)
   - `risk_events` — `(entity_id, event_id, delta, weight, severity, jurisdiction_factor, score_after)`
   - `alerts` — matches Alert schema; `band` as CHECK constraint
   - `sar_draft` — with `version` int and self-referencing `previous_version_id` (SAR edit history from activity 5.2)
   - `audit_log` — `seq` autoincrement, `entry_hash`, `prev_hash` columns **now** (hash-chaining logic itself is Dev 3's Sprint 3 job, but the columns must exist so no migration is needed)
   - `sanctions_cache` — `(name, name_normalized, aliases, list_source, sanction_program, list_version, active)` with index on `name_normalized`
3. **`repositories/unit_of_work.py`** — context-manager UoW wrapping a session: `with UnitOfWork() as uow: uow.alerts.add(...); uow.commit()`
4. **One repository per aggregate** — minimal CRUD only: `add`, `get`, `list` with basic filters (e.g. `alert_repo.list(band=..., status=...)`, `event_repo.get_unprocessed(limit=50)`). No business logic in repos.
5. **`data/seed/seed_entities.py`** — load the synthetic KYC profiles CSV → `entities` table. Compute baseline score from flags: `base = pep_flag*15 + fatf_country_flag*10 + sector_risk_map[sector_risk]`. Mark high-risk subset (`pep OR fatf OR sector_risk == 'High'`) as `watched=True`. Weights read from `policy.yaml`.
6. **`policy.yaml` stub** — risk weights, band thresholds (40/60/80), so seed script and Sprint 2 scoring engine share one file:
   ```yaml
   weights: {pep_flag: 15, fatf_country_flag: 10, transaction_anomaly: 20, adverse_media: 12, sanctions_hit: 40}
   sector_risk: {Low: 0, Medium: 5, High: 12}
   bands: {medium: 40, high: 60, critical: 80}
   ```
7. **`tests/test_repositories.py`** — round-trip test per table; duplicate `content_hash` insert raises IntegrityError; WAL mode assertion.

### Definition of done
- `python -m data.seed.seed_entities` creates the DB, seeds entities, prints watched count
- All repo tests pass
- Schema announced as **frozen** in team chat by Hour 2.5

### Independent — no waiting on anyone after schemas are frozen.

---

## 3. Dev 2 — Infrastructure Mocks (Broker, Cache, LLM Gateway)

**Folder owned:** `app/infrastructure/`

**Why critical:** The LLM Gateway's degradation ladder (retry → model fallback → cached response → degrade-to-review-queue) is in the component table as a first-class behavior — it must be built into the gateway's skeleton **now**, not bolted on when real Gemini calls arrive in Sprint 3.

### Tasks

1. **`broker.py` — AsyncioBroker**
   - `subscribe(topic) -> asyncio.Queue`, `publish(topic, payload)`, `unsubscribe(topic, queue)`
   - Topics to register up front (from sequence diagrams 6.1/6.2): `alert.new`, `alert.updated`, `sar.ready`, `entity.updated`, `system.health`
   - Non-blocking publish: a slow/dead subscriber queue must never stall the pipeline — use `put_nowait` with drop-and-log on full queues
2. **`cache.py` — LocalMemoryCache**
   - `get(key)`, `set(key, value, ttl_seconds)`, `invalidate(prefix)` — dict + expiry timestamps, cleanup on read. Used for LLM response caching and sanctions ETag storage later.
3. **`llm_gateway.py` — LLMGateway class (the big one)**
   - Single public method: `async complete(prompt, *, schema: Type[BaseModel], task_tag: str) -> GatewayResult`
   - `GatewayResult` = `{ok, data, degraded (bool), attempts, model_used, from_cache}`
   - Internal ladder, fully implemented against the mock:
     1. call primary model (mock "gemini-3.1-flash-lite") with retry ×2 + exponential backoff
     2. on failure → fallback model (mock "gemini-flash")
     3. on failure → check LocalMemoryCache for a same-prompt-hash response
     4. on failure → return `ok=False, degraded=True` → **callers route the item to the human review queue** (this contract is what makes graceful degradation real)
   - Cache every successful response keyed on `sha256(prompt + model)`
   - Validate every response against the passed Pydantic `schema`; validation failure counts as a call failure (triggers ladder)
4. **`llm_mock.py`** — canned JSON keyed by `task_tag`:
   - `resolver_verdict` → `{"match": true, "confidence": 0.93, "reasoning": "..."}`
   - `classify_event` → `{"event_type": "adverse_media_fraud", "severity": "high"}`
   - `sar_narrative` → `{"narrative": "...", "citations": [...]}`
   - Add a **failure injection switch** (`LLM_MOCK_FAIL_RATE=0.3` env var) so the ladder is actually exercised in tests
5. **`tests/test_infrastructure.py`** — broker fan-out to 2 subscribers; cache TTL expiry; gateway falls through all 4 ladder rungs when mock is forced to fail; schema-invalid response triggers retry.

### Definition of done
- With `LLM_MOCK_FAIL_RATE=1.0`, `complete()` returns `degraded=True` without raising
- Broker demo: publish `alert.new`, two subscribers both receive it

### Independent — zero dependencies on other devs. Pure Python, can start at Hour 0.

---

## 4. Dev 3 — Knowledge Layer (ChromaDB + chunker + embedder + mock retriever)

**Folder owned:** `knowledge/`

**Why now:** The Resolver agent (Sprint 3) needs top-3 entity-card retrieval; the Reporter needs the regulatory corpus. Standing up all 3 collections and the GDPR/PrivacyQA chunking prep now means Sprint 3 agents plug straight in. This work is fully isolated — perfect parallel track.

### Tasks

1. **`store.py`** — ChromaDB persistent client (`data/chroma/`), create-or-get all **3 collections at startup**: `entity_cards`, `event_context`, `regulatory_corpus`. Expose `get_collection(name)`.
2. **`embedder.py`** — thin wrapper over Chroma's default embedding function behind our own interface (`embed(texts) -> vectors`), so a swap to Gemini embeddings later touches one file.
3. **`chunker.py`** — two strategies:
   - `chunk_entity_card(entity: EntityProfile) -> str` — render one entity into a compact text card: name, aliases, country, sector, flags, known directors ("card" = the document stored per entity)
   - `chunk_regulatory(text, max_tokens=350, overlap=50)` — sliding-window chunker for GDPR articles / PrivacyQA pairs, preserving article numbers in metadata (`{"source": "GDPR", "article": "30"}`) — **citations depend on this metadata**
4. **Populate `entity_cards` with real data this sprint:** after Dev 1's seed runs (≈ Hour 3), write `knowledge/index_entities.py` that reads watched entities from SQLite and upserts cards into `entity_cards`. (Until then, index 10 handwritten fake entities so the retriever is testable at Hour 1.)
5. **`retriever.py`** — `retrieve_entity_candidates(event_text, k=3) -> [{entity_id, card_text, similarity}]` — the exact shape the Resolver consumes in sequence diagram 6.1. Also stub `retrieve_regulatory(query, k=4)` returning canned GDPR passages for now.
6. **`prep_regulatory.py`** — start the GDPR/PrivacyQA/OPP-115 chunking prep: load the provided dataset files, run the chunker, print chunk counts and a sample. Actual full indexing can finish in Sprint 2/3, but the parsing of the dataset formats (the fiddly part) is done now.
7. Smoke test: index 10 entities → query "fraud investigation into Acme Holdings" → top-3 includes Acme.

### Definition of done
- All 3 collections exist and survive process restart (persistence verified)
- `retrieve_entity_candidates()` returns correctly-shaped top-3 on seeded entities
- Regulatory chunker produces metadata-tagged chunks from at least the GDPR file

### Dependency: soft dependency on Dev 1's seed at Hour 3 (works with fake entities before that).

---

## 5. Dev 4 — API Shell (FastAPI scaffold + hardcoded controllers + dummy SSE)

**Folders owned:** `app/main.py`, `app/config.py`, `app/api/`

**Why critical:** Dev 5's entire track blocks on two things from Dev 4: the endpoints existing (any JSON) and the SSE stream emitting. **Ship the dummy SSE endpoint first**, before the other controllers.

### Tasks (in order)

1. **`app/main.py`** — FastAPI app, CORS for the Vite dev origin (`http://localhost:5173`), `lifespan` context that (for now) just logs startup — APScheduler loops slot in here in Sprint 2. Mount all routers.
2. **`app/config.py`** — pydantic-settings: `DB_PATH`, `GEMINI_API_KEY`, `LLM_MOCK_FAIL_RATE`, `SSE_HEARTBEAT_SECONDS`.
3. **`api/sse.py` — SHIP BY HOUR 1.** `GET /api/stream` using `StreamingResponse` (`text/event-stream`):
   - heartbeat comment every 15s (keeps proxies alive)
   - a fake `alert.new` event every 10s with a full Alert-schema payload
   - **wire it to Dev 2's AsyncioBroker from day one**: subscribe to all topics, forward to the client — the "dummy" part is just a background task publishing fake alerts into the broker. Then Sprint 3 needs zero changes here.
4. **`api/health.py`** — `/health` returning `{status, db (can it open?), version}`.
5. **Hardcoded controllers** — each returns JSON that validates against the frozen `app/schemas/` models (import and actually validate — this is the point):
   - `GET /api/alerts?band=&status=` → list of 6–8 fake Alerts across all 3 bands, with evidence arrays
   - `GET /api/alerts/{id}` → one Alert with full evidence bundle
   - `POST /api/alerts/{id}/dismiss` and `/escalate` → echo + fake audit entry
   - `GET /api/entities/{id}` → EntityProfile + fake timeline (interleaved media + transaction events — matching the two-source timeline the demo needs)
   - `GET /api/sar` and `GET /api/sar/{id}` → SARDraft with narrative + regulatory_basis citations
   - `POST /api/sar/{id}/approve|reject|edit` → echo with version bump
   - `GET /api/audit?entity_id=` → fake hash-chained entries (fake hashes fine, shape correct)
   - `GET /api/watchlist`, `POST /api/watchlist` → entity list / add
6. **`tests/test_api_shapes.py`** — for every GET endpoint: response parses into its Pydantic schema. This test is the tripwire that keeps mock payloads honest until Sprint 3 swaps in real services.

### Definition of done
- `uvicorn app.main:app --reload` runs; `/docs` shows all routes
- `curl -N localhost:8000/api/stream` shows heartbeats + a fake alert every 10s
- All shape tests green

### Dependencies: schemas (Hour 1.5, co-authored); Dev 2's broker interface (agree on `subscribe/publish` signature verbally at Hour 0 — 5-minute conversation).

---

## 6. Dev 5 — Frontend Shell (React + Vite + Tailwind + Router + SSE)

**Folder owned:** `frontend/`

### Tasks

1. **Scaffold (Hour 0–0.5):** `npm create vite@latest frontend -- --template react`, add Tailwind, React Router. Commit lockfile immediately.
2. **`App.jsx` + `components/Layout.jsx`** — persistent sidebar with 5 nav links, header with system-status dot (green/amber/red — driven by SSE connection state), dark-friendly palette (compliance dashboards read better dark; also demos well).
3. **Five route pages**, each with static structure and placeholder data hardcoded **in the same shapes as the frozen schemas** (copy from `app/schemas/` docstrings):
   - `AlertQueue.jsx` — table: entity, band chip (color by band: amber/orange/red), score, event type, time, dismiss/escalate buttons (no-op). Filter tabs by band.
   - `EntityTimeline.jsx` — entity header card (flags as badges) + vertical timeline list mixing media events and transaction anomalies (the two-source timeline).
   - `SARReview.jsx` — two-pane: narrative text (editable textarea) left, evidence citations + regulatory-basis list right; approve/reject/edit buttons.
   - `AuditTrail.jsx` — monospace table with `seq, actor, action, hash-prefix, time`, and a "verify chain" button (no-op).
   - `AdminWatchlist.jsx` — entity table with watched toggle + "inject synthetic event" button (no-op — becomes the demo trigger in Sprint 3).
4. **`hooks/useSSE.js` — the sprint's key deliverable.** Wrap `EventSource('/api/stream')`:
   - parse named events (`alert.new`, `alert.updated`, `sar.ready`)
   - expose `{connected, lastEvent, events[]}`
   - handle auto-reconnect state (EventSource retries natively — surface the state to the status dot)
   - **Prove it end-to-end:** AlertQueue shows a toast + prepends a row when Dev 4's dummy `alert.new` arrives. This is the sprint's integration moment.
5. **`api/client.js`** — minimal `fetch` wrapper with base URL from env (`VITE_API_URL`). Wire AlertQueue and EntityTimeline to the real (hardcoded) endpoints if time allows; otherwise Sprint 3.
6. Vite dev-server proxy for `/api` → `localhost:8000` to dodge CORS during dev.

### Definition of done
- All 5 pages render and navigate
- Status dot turns green when backend is up; new fake alert appears in AlertQueue every 10s without refresh

### Dependency: Dev 4's dummy SSE endpoint (Hour 1). Before that, everything else proceeds on hardcoded data.

---

## 7. Timeline & Sync Points

| Hour | Milestone |
|---|---|
| 0:00 | Repo skeleton committed; everyone pulls; Dev 4 + Dev 2 agree broker signature (5 min) |
| 0:00–1:30 | Dev 1 + Dev 4 pair on `app/schemas/` → **contracts frozen** · Devs 2, 3, 5 start independently |
| 1:00 | Dev 4 ships dummy SSE endpoint → unblocks Dev 5's `useSSE` |
| 2:30 | Dev 1 announces **schema frozen**; DB creates + seeds |
| 3:00 | Dev 3 runs `index_entities.py` against Dev 1's seeded DB |
| 3:30–4:00 | **Integration checkpoint (all 5):** backend up → `/health` green → frontend loads all 5 pages → dummy alert appears live in AlertQueue → each dev demos their DoD in 2 minutes |

## 8. What is deliberately NOT in Sprint 1
No real LLM calls, no scoring math, no fuzzy screening, no agents, no SAML-D processing, no real audit hashing (columns only), no React Flow. Resist scope creep — the whole value of this sprint is that Sprint 2 starts with zero plumbing work.

## 9. Sprint 2 preview (so people build the right seams)
- Dev 1 → Rule/Confidence/Policy engines in `app/services/scoring/` (reads `policy.yaml`)
- Dev 2 → verification/credibility scoring feeding Resolver confidence bands
- Dev 3 → explainability trace generation
- Dev 4 → FeedAdapter interface + ProvidedDatasetAdapter + SanctionsListAdapter + start TransactionAdapter (incl. `prep_transactions.py` sampling + `account_entity_map` population + synthetic directors script riding along)
- Dev 5 → React Flow Decision Graph against Dev 3's trace shape
