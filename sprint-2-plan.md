# Sprint 2 — Core Engines (Day 1, Afternoon ≈ 4–5 hours)

**Project:** Continuous KYC Autonomous Auditor (CXKYC) — Tech Mahindra CODE Hackathon, Challenge 3

**Sprint goal:** Real data flows end-to-end through real deterministic logic — no agents yet. By end of sprint: the provided datasets are ingested through actual FeedAdapters into `events_raw`, the Scoring Engine computes real deltas/bands/velocity from `policy.yaml`, the verification layer produces confidence scores, explainability traces exist for every decision, and the frontend renders a live React Flow Decision Graph from a real trace payload. The LLM is still mocked (Dev 2's Sprint 1 gateway) — Sprint 3 makes it live.

**Entering condition (from Sprint 1):** schemas frozen, DB seeded with entities, dummy SSE flowing, all endpoints returning shape-correct fakes, ChromaDB collections standing, LLM Gateway ladder working against mocks.

---

## 0. New Folders This Sprint

```
app/
├── services/
│   ├── scoring/                     # Dev 1
│   │   ├── __init__.py
│   │   ├── rule_engine.py           # delta = weight × severity × jurisdiction
│   │   ├── policy.py                # policy.yaml loader + hot-reload
│   │   ├── velocity.py              # events-per-window computation
│   │   └── bands.py                 # score → medium/high/critical
│   │
│   ├── verification/                # Dev 2
│   │   ├── __init__.py
│   │   ├── credibility.py           # source credibility scoring
│   │   ├── fact_check.py            # cross-source corroboration
│   │   └── confidence.py            # combined confidence → 3-band output
│   │
│   ├── explainability/              # Dev 3
│   │   ├── __init__.py
│   │   ├── trace.py                 # DecisionTrace builder
│   │   ├── counterfactual.py        # "why NOT" reasoning for dismissals
│   │   └── narrator.py              # score-math → human sentence rendering
│   │
│   ├── screening.py                 # Dev 4 — rapidfuzz pre-filter
│   │
│   └── ingestion/                   # Dev 4
│       ├── __init__.py
│       ├── base.py                  # FeedAdapter ABC + registry
│       ├── provided_dataset.py      # KYC profiles → entities/events
│       ├── sanctions_list.py        # ETag + diff refresh (seq 6.3)
│       ├── transactions.py          # SAML-D TransactionAdapter (start)
│       ├── detectors/               # rule-based typologies
│       │   ├── __init__.py
│       │   ├── structuring.py
│       │   ├── rapid_movement.py
│       │   └── high_risk_corridor.py
│       └── inject.py                # InjectAdapter (admin demo trigger)
│
data/
├── prep/
│   ├── prep_transactions.py         # Dev 4 — SAML-D stratified sampler
│   ├── build_account_map.py         # Dev 4 — account → entity synthetic mapping
│   └── gen_directors.py             # Dev 4 — synthetic entity_persons seed
│
app/schemas/
└── traces.py                        # ★ NEW frozen contract — DecisionTrace (Dev 3 + Dev 5, Hour 0)

frontend/src/
├── components/
│   ├── DecisionGraph.jsx            # Dev 5 — React Flow
│   ├── TraceNode.jsx                # custom node types
│   └── EvidenceCard.jsx
└── (React Flow, Axios, React Query added to package.json)
```

---

## 1. The One Shared Task (Hour 0 → 0:45): Freeze the DecisionTrace Contract

Sprint 1's lesson repeats: **Dev 3 and Dev 5 pair for 30–45 minutes** to freeze `app/schemas/traces.py` before splitting. The React Flow graph is built entirely against this shape, and Dev 3's trace builder emits it. Everyone else starts immediately.

Lock this shape (a directed graph, not a list — React Flow consumes nodes + edges natively):

```python
class TraceNode(BaseModel):
    id: str
    kind: Literal["event", "screen", "resolve", "verify", "classify",
                  "score", "propagate", "decision"]
    label: str                 # short: "Fuzzy match 87"
    detail: str                # full sentence: "Name 'Acme Hldgs' matched watchlist entry 'Acme Holdings' at token_set_ratio 87"
    values: dict               # machine-readable: {"weight": 12, "severity": 0.8, "jurisdiction": 1.3, "delta": 12.5}
    outcome: Literal["pass", "fail", "branch"] | None

class TraceEdge(BaseModel):
    source: str; target: str
    label: str | None          # "confidence 0.93 → proceed"

class DecisionTrace(BaseModel):
    trace_id: str
    event_id: str
    entity_id: str | None
    final_outcome: Literal["screened_out", "dismissed", "review_queued",
                           "alert_medium", "alert_high", "alert_critical"]
    counterfactual: str | None # only for dismissals: "would have alerted if confidence ≥ 0.75 because..."
    nodes: list[TraceNode]
    edges: list[TraceEdge]
    created_at: datetime
```

Also add `trace: DecisionTrace | None` to the Alert schema, and `GET /api/traces/{event_id}` to Dev 4's route list. **Frozen by Hour 0:45.**

---

## 2. Dev 1 — Risk Engine (Rule / Policy / Velocity / Bands)

**Folder owned:** `app/services/scoring/`

**Non-negotiable principle from the design doc:** score math never touches the LLM. Every function here is pure and deterministic — same inputs, same output, unit-testable without any mock. This is the explainability backbone; judges will probe "how do we know the AI didn't make up the score?"

### Tasks

1. **`policy.py` — PolicyLoader with hot-reload**
   - Parse `policy.yaml` into a frozen Pydantic `RiskPolicy` model (weights, sector map, band thresholds, velocity window config, jurisdiction factors)
   - Hot-reload: watch file mtime; expose `get_policy()` that re-reads on change; publish `policy.reloaded` on the broker so the dashboard can show "policy updated" (this is UC10's backend half — the admin edit UI can wait)
   - Extend `policy.yaml` with what Sprint 1 stubbed: `jurisdiction_factors` (FATF-listed country → 1.3, else 1.0), `velocity: {window_hours: 72, multiplier_threshold: 3}`, per-event-type severity defaults
2. **`rule_engine.py` — the core formula**
   - `compute_delta(event_type, severity: float, jurisdiction_factor: float, policy) -> ScoreDelta`
   - `delta = policy.weights[event_type] × severity × jurisdiction_factor`
   - Returns not just the number but the **full breakdown** `{weight, severity, jurisdiction_factor, delta}` — this dict goes verbatim into `risk_events` and into Dev 3's trace nodes. Never return a bare float.
   - `apply_delta(entity_id, score_delta, uow)` — write `risk_events` row, update `entities.current_score`, clamp 0–100
3. **`velocity.py`**
   - `compute_velocity(entity_id, window_hours, uow) -> VelocityResult` — count risk_events in trailing window vs the entity's historical baseline rate; return `{count, baseline, multiplier}`
   - Velocity breach (multiplier ≥ threshold) can promote a band one level even when raw score doesn't cross — implement as an explicit, traced rule
4. **`bands.py`**
   - `resolve_band(score, velocity, sanctions_direct_hit: bool, policy) -> Band`
   - Order of precedence (from activity 5.1): direct sanctions hit → critical regardless of score; else score thresholds; else velocity promotion. Each branch returns which rule fired (for the trace).
5. **Network Propagator (assigned here per the roadmap's "decide now" note)** — `propagator.py` in the same folder:
   - `propagate(entity_id, delta, uow)` — 1-hop only: find related entities via shared `entity_persons` rows, apply `delta × policy.propagation_factor` (add `propagation_factor: 0.35` to policy.yaml) with `indirect=True` flag on the risk_event, audit each bump
   - Guard: never propagate a propagation (check `indirect` flag) — cycles impossible by construction
   - **Depends on Dev 4's `gen_directors.py` output (Hour ~2)** — until then, test against 3 handwritten entity_persons rows
6. **Tests** — table-driven: 10 delta computations with known answers; band precedence matrix (sanctions beats score beats velocity); velocity promotion case; propagation applies to 1 hop and stops; policy hot-reload picks up a changed weight without restart.

### Definition of done
- Feed a classified fake event → correct `risk_events` row with full breakdown, entity score updated, correct band, propagation bumps a related entity
- Editing `policy.yaml` while running changes the next computation

### Dependencies: `gen_directors.py` seed from Dev 4 at ~Hour 2 (soft — handwritten rows until then).

---

## 3. Dev 2 — Verification Layer (credibility, corroboration, confidence)

**Folder owned:** `app/services/verification/`

**Role in the system:** produces the confidence number that drives the three-way branch in activity diagram 5.1 — below 0.40 dismiss, 0.40–0.75 human review queue, above 0.75 proceed. In Sprint 3 the Resolver combines this with the LLM verdict; this sprint it must work standalone on deterministic signals.

### Tasks

1. **`credibility.py` — source credibility scoring**
   - Static tier table: official sanctions lists = 1.0, major wire/regulatory news = 0.9, regional press = 0.7, blogs/unknown RSS = 0.4, injected demo events = configurable
   - `score_source(raw_event) -> float` from `raw_event.source` + domain heuristics; unknown sources get 0.5 with a `low_credibility` flag that surfaces in the trace
2. **`fact_check.py` — corroboration**
   - `corroborate(event, uow) -> CorroborationResult` — search `events_raw` for other events about the same entity within ±72h from *different* sources (match on normalized names + fuzzy)
   - Returns `{corroborating_count, sources[], corroboration_boost}` — 0 sources = no boost, 1 = +0.10, 2+ = +0.20 (put these in policy.yaml too, everything tunable lives in one file)
3. **`confidence.py` — the combiner**
   - `compute_confidence(match_score: float, credibility: float, corroboration: CorroborationResult) -> ConfidenceResult`
   - Sprint 2 formula (no LLM): `confidence = normalize(fuzzy_match_score) × credibility + corroboration_boost`, clamped 0–1
   - **Design the signature for Sprint 3 now:** accept an optional `llm_verdict_confidence: float | None` parameter that, when present, blends in (e.g. `0.6 × llm + 0.4 × deterministic`). Sprint 3 then changes one call site, not this module.
   - `to_band(confidence) -> Literal["dismiss", "review", "proceed"]` with thresholds from policy.yaml (0.40 / 0.75)
   - Every result carries its own breakdown dict for the trace, same discipline as the scoring engine
4. **Wire the degraded-LLM path:** when Sprint 3's gateway returns `degraded=True`, the pipeline must fall back to this deterministic confidence with a forced ceiling of 0.74 (i.e. can never auto-proceed without the LLM — it goes to human review). Implement the ceiling flag now: `compute_confidence(..., degraded=False)`.
5. **Tests** — high-credibility corroborated event lands "proceed"; single blog source lands "review"; garbage match lands "dismiss"; `degraded=True` caps at review even with perfect inputs.

### Definition of done
- Given a fake screened event + seeded events_raw, returns a ConfidenceResult with band + breakdown
- Degraded ceiling verified by test

### Independent — pure logic against Sprint 1's repos. No waiting.

---

## 4. Dev 3 — Explainability (decision traces + counterfactuals)

**Folder owned:** `app/services/explainability/` (+ co-owns `schemas/traces.py` freeze at Hour 0)

**Role:** this is what turns "score 0.87" into "structuring: 14 txns of ₹49k in 6h." Every component built this sprint (scoring, verification, screening, detectors) emits breakdown dicts — Dev 3 turns those into one coherent DecisionTrace per event, persisted and served to the frontend.

### Tasks

1. **`trace.py` — TraceBuilder**
   - Builder pattern accumulated through the pipeline: `t = TraceBuilder(event); t.add("screen", label=..., values=fuzzy_result); t.add("verify", values=confidence.breakdown); ... t.finalize(outcome)`
   - Auto-generates edges in pipeline order; branch nodes (confidence band, score band) get labeled edges for the path taken **and** grayed edges for paths not taken (React Flow will render the full decision shape — this is the visual payoff)
   - `finalize()` validates against the frozen schema, persists to a new `decision_traces` table (**coordinate with Dev 1 — one small schema addition, agree at Hour 0:45; it's a single JSON-blob column keyed by event_id, low risk**)
2. **`narrator.py` — values → sentences**
   - Per-node-kind template functions that render breakdown dicts into the `detail` strings: scoring node → "adverse_media (weight 12) × severity 0.8 × jurisdiction 1.3 = +12.5 → score 66 (high)"; detector node → "structuring: {n} transactions of ~{amt} within {window}" (consumes Dev 4's detector evidence payloads — **agree the evidence dict keys with Dev 4 at Hour 1, 10-minute conversation**)
   - No LLM anywhere in this module. Templates only. The LLM narrative layer is the Reporter's job in Sprint 3; traces must be trustworthy without it.
3. **`counterfactual.py`**
   - For `dismissed` and `screened_out` outcomes: generate the "what would have changed the outcome" string deterministically by inspecting which gate failed: "Dismissed at confidence 0.31. Would have proceeded if: source credibility ≥ 0.7 (was 0.4, single uncorroborated blog) or fuzzy match ≥ 80 (was 64)."
   - This is the false-positive-dismissal demo moment — make the sentences good.
4. **Integration shim:** a `traced_pipeline(event)` function that chains screening → verification → (mock classify) → scoring → propagation with the TraceBuilder woven through — this is the deterministic skeleton the Sprint 3 LangGraph replaces, and it's how the whole team integration-tests today.
5. **Hand Dev 5 a golden fixture by Hour 2:** `tests/fixtures/trace_critical.json` and `trace_dismissed.json` — real serialized traces. Dev 5 builds the graph against these files before the API endpoint exists.
6. **Tests** — trace for a full-path critical event has all node kinds; dismissed trace has counterfactual; every node's `detail` is non-empty; schema round-trips.

### Definition of done
- `traced_pipeline(fake_event)` produces a persisted, schema-valid trace end-to-end
- Golden fixtures delivered to Dev 5 by Hour 2

### Dependencies: breakdown-dict shapes from Dev 1 (scoring) and Dev 2 (confidence) — both are producing them by design; agree key names in a 10-minute three-way at Hour 1.

---

## 5. Dev 4 — Ingestion & Adapters (the heaviest track — start with data prep)

**Folders owned:** `app/services/ingestion/`, `app/services/screening.py`, `data/prep/`

**Sequencing logic:** SAML-D prep is the known heavy lift (9.5M rows) and `gen_directors.py` unblocks Dev 1's propagator — so **data prep scripts run first, in the background, while adapter interfaces are written.** Never load the full SAML-D CSV interactively.

### Tasks (in order)

1. **Kick off `data/prep/prep_transactions.py` immediately (Hour 0):**
   - Chunked stratified sampler exactly per the analysis doc: keep ALL `Is_laundering=1` rows, sample 2% of normals, `chunksize=500_000`, output `data/processed/txn_sample.parquet`
   - Start it running, then move on — check back at each hour mark
2. **`data/prep/gen_directors.py` (Hour 0:30 — Dev 1 is waiting on this):**
   - For 15–20 watched entities generate 2–4 synthetic directors each into `entity_persons`
   - Deliberately plant: (a) 3–4 names that exactly match OpenSanctions/OFAC entries, (b) 2–3 fuzzy variants (transliteration/typo), (c) **one same-name-different-person trap** (matching name, different DOB/nationality) — this trap is the entity-resolution demo case
   - Ensure at least 2 pairs of entities **share a director** — otherwise the Network Propagator has nothing to propagate
3. **`data/prep/build_account_map.py` (Hour 1):**
   - Deterministic synthetic mapping: suspicious-heavy SAML-D accounts → watched high-risk entities, plus a mix of normal accounts (realistic false-positive surface) → `account_entity_map` table
   - Seeded RNG (`random.seed(42)`) so reruns are reproducible for demo rehearsal
4. **`ingestion/base.py` — FeedAdapter ABC + registry (Hour 1:30):**
   - `class FeedAdapter(ABC): name: str; schedule_seconds: int; async fetch() -> list[RawEvent]`
   - Shared helpers on the base: SHA-256 content hashing, HTML stripping, name normalization, UTC coercion — every adapter's output is dedupe-ready by construction
   - Failure wrapper per the component table: retry with backoff, `consecutive_failures` counter, emit `system.health` warning (stale-data) on the broker after 3 failures, **never write partial data over cache**
   - Registry + APScheduler wiring: register adapters into the FastAPI lifespan as Loop A (per-adapter schedule) and add Loop B skeleton (5s poll of unprocessed events → for now, route into Dev 3's `traced_pipeline`)
5. **`ingestion/provided_dataset.py` — ProvidedDatasetAdapter:**
   - Re-runs entity seeding idempotently and emits day-0 `RawEvent`s for entities with `sanctions_flag=1` (the "system started, immediately found existing exposures" demo opener)
6. **`ingestion/sanctions_list.py` — SanctionsListAdapter (sequence 6.3):**
   - ETag HEAD-check (store ETag in Dev 2's LocalMemoryCache) → skip if unmodified
   - On change: parse → normalize → explode aliases → diff vs active `sanctions_cache` rows → version old rows, insert new → emit one RawEvent per **addition** (reverse screening happens in the pipeline) → audit `list_refreshed` with counts
   - For the hackathon, "external source" = the provided OpenSanctions/OFAC files behind a file:// shim with a fake ETag — the diff logic is what's real
7. **`ingestion/transactions.py` + `detectors/` — start, don't finish:**
   - Replay-clock: stream `txn_sample.parquet` in simulated time (1 day = 30s, configurable)
   - **Rules first, model never this sprint:** implement `structuring.py` (N txns just-under-threshold within window) fully; stub `rapid_movement.py` and `high_risk_corridor.py` with interfaces + TODO (finish in Sprint 3 per roadmap)
   - Detector hit → `RawEvent(event_type="transaction_anomaly", payload={typology, evidence: {n, approx_amount, window_hours, txn_ids}})` — **evidence keys agreed with Dev 3 at Hour 1**
8. **`services/screening.py`** — the rapidfuzz pre-filter (it's pipeline, not adapter, but it's small and Dev 4 owns the pipeline loop): extract name candidates → `token_set_ratio` vs watchlist + sanctions_cache → candidates ≥ 80 pass, else audit `screened_out`
9. **`ingestion/inject.py` — InjectAdapter:** `POST /api/admin/inject` (add route) → hand-crafted RawEvent straight into events_raw with `is_drill` flag support — this is the demo trigger button and Sprint 3's red-team entry point

### Definition of done
- All three prep scripts run: parquet exists, entity_persons seeded (shared directors verified), account map populated
- ProvidedDataset + Sanctions adapters run on schedule; killing the sanctions file source produces a stale-data warning, not corruption
- One structuring detection travels: parquet → detector → RawEvent → screening → traced_pipeline → alert row + SSE

### Dependencies: none inbound. Everyone else depends on Dev 4's seeds — hence data prep first.

---

## 6. Dev 5 — Decision Graph + Live Data Wiring

**Folder owned:** `frontend/`

### Tasks

1. **Install React Flow, Axios, React Query (Hour 0)** — commit lockfile before anything else so no one fights dependency drift later
2. **`components/DecisionGraph.jsx` — the judge-facing centerpiece. Build against Dev 3's golden fixtures, not the live API:**
   - Load `trace_critical.json` / `trace_dismissed.json` from fixtures first; swap to `GET /api/traces/{event_id}` at Hour 3+
   - Custom `TraceNode.jsx` per node kind: event (document icon), screen/verify (gauge-style with the number prominent), score (the formula rendered: weight × severity × jurisdiction = delta), decision (band-colored terminal node)
   - **Taken path bold + colored, not-taken branches gray dashed** — the "the system considered dismissing this and here's why it didn't" visual
   - Click node → side drawer with `detail` sentence + raw `values` table
   - Layout: `dagre` left-to-right auto-layout (pipeline reads as a flow); disable node dragging, enable zoom/pan
   - Counterfactual (when present) rendered as a callout banner under the graph
3. **Wire real data with React Query:**
   - Replace hardcoded page data: AlertQueue → `GET /api/alerts`, EntityTimeline → `GET /api/entities/{id}` (interleaved media + transaction events now real), AuditTrail → `GET /api/audit`, Watchlist → `GET /api/watchlist`
   - Query invalidation on SSE: `alert.new` → invalidate `['alerts']`; `entity.updated` → invalidate that entity — this makes every screen live without polling
4. **AlertQueue → Decision Graph navigation:** each alert row gets a "Why?" button → routes to `/alerts/{id}/trace` rendering the DecisionGraph — this exact click is the demo beat
5. **Admin inject button goes real:** wire the Sprint 1 no-op to `POST /api/admin/inject` with a small form (entity picker + event type + severity) — end-of-sprint integration test uses it
6. **Timeline upgrade:** EntityTimeline visually distinguishes media events vs transaction anomalies (icon + color) on one interleaved axis — the correlated-risk story surface

### Definition of done
- Fixture-driven DecisionGraph renders both golden traces correctly (branching, gray paths, counterfactual banner)
- Inject → alert appears live → click "Why?" → live graph renders the real trace

### Dependencies: traces.py freeze (Hour 0:45, co-authored), golden fixtures from Dev 3 (Hour 2), `/api/traces/{id}` from Dev 4's route additions (Hour 3).

---

## 7. Timeline & Sync Points

| Hour | Milestone |
|---|---|
| 0:00 | Dev 3 + Dev 5 pair on `schemas/traces.py` · Dev 4 launches `prep_transactions.py` in background · Dev 5 installs deps · Devs 1, 2 start engines |
| 0:45 | **DecisionTrace frozen** · Dev 3 + Dev 1 agree `decision_traces` table (5 min) |
| 1:00 | Three-way (Dev 1, 2, 3): breakdown-dict key names agreed · Dev 3 + Dev 4: detector evidence keys agreed |
| 2:00 | Dev 4 ships `gen_directors.py` → unblocks Dev 1's propagator · Dev 3 ships golden fixtures → unblocks Dev 5's graph |
| 3:00 | Dev 4 adds `GET /api/traces/{event_id}` + `POST /api/admin/inject` routes · Dev 5 swaps fixtures → live API |
| 4:00–4:30 | **Integration checkpoint (all 5):** inject a synthetic adverse-media event via the admin UI → screening passes → confidence proceeds → score computed → band assigned → propagation bumps a related entity → alert lands live in AlertQueue via SSE → "Why?" opens the DecisionGraph showing the full deterministic path. Then inject a garbage event → watch it dismiss with a counterfactual. |

## 8. What is deliberately NOT in Sprint 2
No live LLM calls (gateway still mocked), no LangGraph agents (Sprint 3 — `traced_pipeline` is the placeholder), no SAR generation, no audit hash-chaining logic (columns exist, chaining is Dev 3's Sprint 3), no Random Forest model (rules only; RF only if Sprint 3 has slack), no red-team/dormancy, no GDELT/GNews live feeds (adapter ABC supports them; provided datasets are enough for Day 1).

## 9. Sprint 3 preview (build the right seams today)
- Dev 1 → LangGraph AuditorState + supervisor: replaces `traced_pipeline`'s spine; every engine call site becomes an agent tool — keep engine functions pure and stateless today so they lift straight in
- Dev 2 → scenario engine + demo gold: the inject route and replay-clock built today are its levers
- Dev 3 → audit hash-chaining + SAR RAG: chaining slots into the audit repo; SAR pulls `regulatory_corpus` (finish indexing if `prep_regulatory.py` output isn't fully loaded)
- Dev 4 → swap remaining hardcoded controllers for real services + finish the two stubbed detectors
- Dev 5 → SAR review live wiring + `sar.ready` SSE handling
