# System Design Document
## Continuous KYC Autonomous Auditor (CXKYC)

**Tech Mahindra CODE Hackathon — Challenge 3**

---

## 1. System Design Methodology

The system is designed using an **iterative, architecture-first methodology** combining three complementary approaches:

**1.1 Layered Architecture Pattern.** The system is decomposed into five horizontal layers (Client, Application, Agent Runtime, Domain Services, Storage), each with a single responsibility and communicating only with adjacent layers. This enforces separation of concerns and allows each layer to be scaled or replaced independently.

**1.2 Event-Driven Architecture (EDA).** All risk signals — adverse media, sanctions list changes, and transaction anomalies — are normalized into a single canonical `RawEvent` structure and processed through one unified pipeline. New data sources are integrated by implementing a `FeedAdapter` interface, never by modifying the pipeline. This is the core extensibility mechanism of the system.

**1.3 Agent-Oriented Design (Supervisor pattern).** Intelligence is decomposed into four specialist agents (Monitor, Resolver, Investigator, Reporter) orchestrated by a LangGraph supervisor over a shared typed state. Routing is deterministic wherever the decision is unambiguous; the LLM is invoked only for judgments that genuinely require semantic reasoning (entity disambiguation, severity classification, narrative generation).

**Design principles applied throughout:**

| Principle | Application |
|---|---|
| Human-in-the-loop | No SAR is ever auto-filed; every escalation requires human sign-off |
| Explainability by construction | Risk scores are computed by a deterministic rule engine; the LLM explains, it does not decide the arithmetic |
| Append-only auditability | Every AI and human decision is written to a tamper-evident, hash-chained audit log; no record is ever mutated |
| Cost-aware AI | Two-stage screening (fuzzy pre-filter → LLM) ensures LLM calls scale sub-linearly with event volume |
| Fail-safe data handling | Feed failures never corrupt cached data; stale data is surfaced visibly rather than hidden |

**Development process:** requirements analysis (problem-statement decomposition) → architecture definition (this document) → data design → component design → iterative implementation in vertical slices (each slice delivers one end-to-end demonstrable behavior) → integration → demo rehearsal.

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | Vanilla JavaScript (ES6), HTML5, CSS3 | Zero build tooling; SSE-native via `EventSource`; fast to iterate under hackathon constraints |
| Real-time transport | Server-Sent Events (SSE) | Simpler than WebSockets; unidirectional push is sufficient for alert streaming |
| Backend framework | FastAPI (Python 3.11+) | Async-native, automatic OpenAPI docs, Pydantic validation |
| Agent orchestration | LangGraph | Typed shared state, conditional-edge routing, supervisor pattern |
| LLM | Google Gemini (`gemini-3.1-flash-lite` primary, fallback chain) | Cost-efficient; all calls routed through a central LLM Gateway with retry, quota fallback, and response caching |
| Vector store | ChromaDB (3 collections: `entity_cards`, `event_context`, `regulatory_corpus`) | Local, embedded, no infrastructure; semantic entity matching and regulatory RAG |
| Relational store | SQLite (WAL mode) via SQLAlchemy ORM | Zero-ops; WAL enables concurrent dashboard reads during worker writes; ORM makes migration to PostgreSQL a connection-string change |
| Scheduling | APScheduler (asyncio) | Independent ingest and process loops inside the FastAPI lifespan |
| Fuzzy matching | rapidfuzz | High-throughput pre-filter; eliminates ~95% of events before any LLM call |
| ML (transaction monitoring) | scikit-learn (Random Forest) + rule-based typology detectors | Hybrid: model provides recall, rules provide explainable evidence |
| Data preparation | pandas, pyarrow (Parquet) | Stratified sampling of the 9.5M-row SAML-D dataset into a fast-loading working set |
| Configuration | pydantic-settings + YAML risk policy | Runtime-reloadable risk weights and thresholds |
| Datasets | Synthetic KYC profiles, SAML-D, OpenSanctions, OFAC SDN, GDPR/PrivacyQA/OPP-115 | Provided challenge datasets + live-refreshable public sources |

**Production migration path (design intent, not hackathon scope):** SQLite → PostgreSQL; ChromaDB → pgvector; APScheduler → Kafka consumers; SSE fan-out → Redis pub/sub; feed polling → vendor webhooks (Dow Jones, ComplyAdvantage).

---

## 3. System Process Overview

The system operates as three concurrent loops sharing one database:

**Loop A — Ingestion (every 15 s, per adapter schedule).** Each registered `FeedAdapter` (GDELT, GNews, RSS, OpenSanctions, OFAC, TransactionAdapter, InjectAdapter, ProvidedDatasetAdapter) fetches new raw material, normalizes it into `RawEvent` objects (UTC timestamps, stripped HTML, normalized names), and inserts them into `events_raw` guarded by a SHA-256 content-hash uniqueness constraint.

**Loop B — Processing (every 5 s).** Unprocessed events are drawn from `events_raw` and passed through the pipeline: fuzzy screen → LangGraph agent network (resolve → score → route) → alert/SAR outcomes → SSE broadcast. Every stage decision, including dismissals, is appended to the audit log.

**Loop C — Human review (event-driven).** Compliance officers act on alerts and SAR drafts through the dashboard; every human action is recorded in the same audit log, closing the loop and feeding the confidence-calibration metrics.

**Loop D — Self-assessment (scheduled, low frequency).** Two autonomous quality checks run alongside the main loops: the *Red-Team Agent* (nightly or on-demand) injects synthetic evasion attempts through the real pipeline to measure detection quality, and the *Dormancy Detector* (daily) flags watched entities whose media footprint has anomalously vanished — treating the absence of signal as a signal.

---

## 4. Use Case Diagram

```mermaid
graph LR
    CO(["Compliance Officer"])
    ADM(["Administrator"])
    SCH(["Scheduler<br/>(system actor)"])
    REG(["Regulator / Auditor<br/>(secondary actor)"])

    subgraph CXKYC["Continuous KYC Autonomous Auditor"]
        UC1(["View alert queue"])
        UC2(["Review entity risk profile<br/>and timeline"])
        UC3(["Investigate alert<br/>(view evidence bundle)"])
        UC4(["Dismiss / escalate alert"])
        UC5(["Review and edit SAR draft"])
        UC6(["Approve / reject SAR"])
        UC7(["View audit trail"])
        UC8(["Verify audit chain integrity"])
        UC9(["Manage watchlist entities"])
        UC10(["Configure risk policy<br/>(weights, thresholds)"])
        UC11(["Inject synthetic event<br/>(demo / drill)"])
        UC12(["Run red-team drill"])
        UC13(["Ingest and screen<br/>risk signals"])
        UC14(["Refresh sanctions lists<br/>(diff-based)"])
        UC15(["Generate SAR draft"])
        UC16(["Replay decision state<br/>as of past date"])
        UC17(["Detect dormancy signal<br/>(mention-frequency drop)"])
        UC18(["Propagate indirect exposure<br/>to related entities"])
    end

    CO --> UC1
    CO --> UC2
    CO --> UC3
    CO --> UC4
    CO --> UC5
    CO --> UC6
    CO --> UC7
    ADM --> UC9
    ADM --> UC10
    ADM --> UC11
    ADM --> UC12
    SCH --> UC13
    SCH --> UC14
    SCH --> UC17
    REG --> UC7
    REG --> UC8
    REG --> UC16

    UC13 -.->|includes| UC15
    UC13 -.->|includes| UC18
    UC12 -.->|uses| UC11
    UC3 -.->|extends| UC2
    UC6 -.->|includes| UC7
```

**Actor summary:** the *Compliance Officer* is the primary human actor (review and decision workflows); the *Administrator* manages configuration and demo/drill tooling; the *Scheduler* is a system actor driving autonomous behavior; the *Regulator/Auditor* is a secondary actor served by the audit-trail, chain-verification, and decision-replay use cases.

---

## 5. Activity Diagrams

### 5.1 Event Processing Pipeline (core autonomous activity)

```mermaid
flowchart TD
    A(["Start: adapter emits RawEvent"]) --> B["Compute SHA-256 content hash"]
    B --> C{"Hash already<br/>in events_raw?"}
    C -- yes --> D["Discard duplicate<br/>increment counter"] --> Z1(["End"])
    C -- no --> E["Persist to events_raw"]
    E --> F["Extract name candidates<br/>from event text"]
    F --> G["Fuzzy match vs watchlist<br/>rapidfuzz token_set_ratio"]
    G --> H{"Any match with<br/>score 80 or higher?"}
    H -- no --> I["Audit: screened_out"] --> Z2(["End"])
    H -- yes --> J["Invoke LangGraph pipeline"]
    J --> K["Resolver: embed event,<br/>retrieve top-3 entity cards,<br/>LLM verdict with confidence"]
    K --> L{"Confidence?"}
    L -- "below 0.40" --> M["Dismiss with reasoning<br/>and counterfactual explanation"] --> N["Audit: dismissed"] --> Z3(["End"])
    L -- "0.40 to 0.75" --> O["Queue for human review"] --> P["Audit: review_queued"] --> Z4(["End"])
    L -- "above 0.75" --> Q["Classify event type and severity<br/>LLM, structured output"]
    Q --> R["Deterministic scoring:<br/>delta = weight x severity x jurisdiction"]
    R --> S["Update entity risk score,<br/>recompute velocity"]
    S --> S2{"Entity has related parties<br/>via shared directors?"}
    S2 -- yes --> S3["Propagate indirect exposure:<br/>bump related entity scores<br/>with indirect flag and audit"]
    S2 -- no --> T
    S3 --> T{"Score or velocity<br/>band?"}
    T -- "medium, 40 plus" --> U["Create medium alert"]
    T -- "high, 60 plus" --> V["Create high alert<br/>dispatch Investigator async"]
    T -- "critical, 80 plus or<br/>direct sanctions hit" --> W["Create critical alert<br/>dispatch Investigator<br/>trigger SAR draft"]
    U --> X["Broadcast SSE event<br/>append audit entries"]
    V --> X
    W --> X
    X --> Z5(["End"])
```

### 5.2 SAR Review Workflow (human-in-the-loop activity)

```mermaid
flowchart TD
    A(["Start: SAR draft generated<br/>status = pending_review"]) --> B["Officer opens SAR<br/>review screen"]
    B --> C["System displays draft narrative,<br/>evidence citations,<br/>regulatory basis via RAG"]
    C --> D{"Officer decision"}
    D -- edit --> E["Officer edits narrative"]
    E --> F["Save as new version<br/>previous version preserved"]
    F --> C
    D -- request more info --> G["Re-dispatch Investigator<br/>with the officer question"]
    G --> H["Evidence bundle updated"] --> C
    D -- reject --> I["Record rejection and reviewer notes<br/>status = rejected"]
    I --> J["Feed decision into<br/>calibration metrics"]
    D -- approve --> K["Record approval and sign-off<br/>status = approved"]
    K --> J
    J --> L["Append hash-chained<br/>audit entry"]
    L --> M(["End"])
```

---

## 6. Sequence Diagrams

### 6.1 Adverse Media Event → Live Alert (primary flow)

```mermaid
sequenceDiagram
    autonumber
    participant FA as Feed Adapter
    participant DB as SQLite
    participant W as Process Worker
    participant SCR as Screening Service
    participant SUP as LangGraph Supervisor
    participant RES as Resolver Agent
    participant CH as ChromaDB
    participant LLM as LLM Gateway
    participant SC as Scoring Engine
    participant SSE as SSE Broadcaster
    participant UI as Dashboard

    FA->>DB: INSERT RawEvent, hash-deduped
    W->>DB: poll unprocessed events
    W->>SCR: screen event
    SCR->>SCR: fuzzy match vs watchlist via rapidfuzz
    SCR-->>W: candidate entity ids with match scores
    W->>SUP: invoke AuditorState
    SUP->>RES: route to resolve entity
    RES->>CH: query entity_cards, top 3
    CH-->>RES: candidate cards with similarity
    RES->>LLM: disambiguation prompt, JSON verdict requested
    LLM-->>RES: verdict match true, confidence 0.93, reasoning
    RES-->>SUP: state resolved_entity_id set
    SUP->>LLM: classify event type and severity
    LLM-->>SUP: event_type and severity
    SUP->>SC: compute score delta, deterministic
    SC->>DB: INSERT risk_event, UPDATE entity score
    SC-->>SUP: new score 78, band critical
    SUP->>DB: INSERT alert and audit entries in batch
    SUP->>SSE: publish alert.new
    SSE-->>UI: SSE push, no page refresh
    UI->>UI: alert appears, timeline updates
```

### 6.2 Critical Alert → Investigation → SAR Approval

```mermaid
sequenceDiagram
    autonumber
    participant SUP as Supervisor
    participant INV as Investigator Agent
    participant CH as ChromaDB
    participant DB as SQLite
    participant REP as Reporter Agent
    participant LLM as LLM Gateway
    participant SSE as SSE Broadcaster
    participant CO as Compliance Officer

    SUP->>INV: dispatch async on critical alert
    INV->>DB: fetch historical risk_events for entity
    INV->>DB: fetch related entities via shared directors
    INV->>CH: retrieve event_context snippets via RAG
    INV->>LLM: compile evidence bundle
    LLM-->>INV: structured evidence with source, snippet, relevance
    INV->>DB: attach evidence to alert
    INV->>SSE: publish alert.updated
    SUP->>REP: trigger SAR draft on threshold breach
    REP->>CH: retrieve regulatory_corpus passages, GDPR and PrivacyQA
    REP->>LLM: generate SAR narrative with citations
    LLM-->>REP: draft narrative and regulatory basis
    REP->>DB: INSERT sar_draft v1, pending_review
    REP->>SSE: publish sar.ready
    SSE-->>CO: notification on dashboard
    CO->>DB: edit narrative, saved as v2
    CO->>DB: POST approve decision on SAR
    DB->>DB: append hash-chained audit entry as human actor
```

### 6.3 Automated Sanctions List Refresh (diff-based)

```mermaid
sequenceDiagram
    autonumber
    participant SCH as Scheduler every 6h
    participant SA as SanctionsListAdapter
    participant EXT as External list source
    participant DB as Sanctions cache DB
    participant PIPE as Event Pipeline

    SCH->>SA: run
    SA->>EXT: HEAD request for ETag check
    alt ETag unchanged
        EXT-->>SA: not modified
        SA-->>SCH: no-op, zero bytes downloaded
    else List changed
        EXT-->>SA: full list download
        SA->>SA: parse and normalize names
        SA->>DB: diff vs active cache entries
        DB-->>SA: added, removed, modified sets
        SA->>DB: version old rows, insert new list_version rows
        SA->>PIPE: emit RawEvent per addition
        Note over PIPE: Reverse screening - each new sanctioned name<br/>is matched against the FULL existing watchlist,<br/>giving bidirectional coverage
        SA->>DB: audit entry list_refreshed with counts and version
    end
```

### 6.4 Red-Team Drill (self-testing detection quality)

```mermaid
sequenceDiagram
    autonumber
    participant SCH as Scheduler nightly
    participant RT as Red-Team Agent
    participant LLM as LLM Gateway
    participant IA as InjectAdapter
    participant PIPE as Event Pipeline
    participant DB as SQLite
    participant UI as Dashboard

    SCH->>RT: run drill
    RT->>DB: sample watched entities and sanctioned names
    RT->>LLM: generate evasion variants - transliterations,<br/>shell names, typo squats, split identities
    LLM-->>RT: N synthetic evasion events
    RT->>IA: inject events with is_drill true
    IA->>PIPE: RawEvents enter the normal pipeline
    Note over PIPE: Drill events are processed identically<br/>but flagged - they never create<br/>real alerts or SARs
    PIPE->>DB: per-event outcome recorded
    RT->>DB: compare outcomes vs expected per variant class
    RT->>DB: write drill report and audit entry
    UI->>DB: fetch detection health metric
    UI-->>UI: show detection health, 17 of 20 caught,<br/>with per-class miss analysis
```

### 6.5 Dormancy Detection (absence-of-signal monitoring)

```mermaid
flowchart TD
    A(["Scheduled check: daily<br/>per watched entity"]) --> B["Compute historical baseline:<br/>mean mentions per week<br/>over trailing 90 days"]
    B --> C["Compute recent window:<br/>mentions in last 14 days"]
    C --> D{"Recent rate below 25% of baseline<br/>AND baseline at least 2 per week?"}
    D -- no --> E(["End: normal activity"])
    D -- yes --> F["Raise dormancy flag<br/>no score change"]
    F --> G["Create low-priority<br/>investigation nudge"]
    G --> H["Audit: dormancy_flagged<br/>with baseline vs recent stats"]
    H --> I(["End"])
```

The dormancy check deliberately does **not** alter the risk score — silence is a soft signal warranting attention, not a scored risk event. The `baseline >= 2/week` guard prevents false flags on entities that were never actively covered.

---

## 7. Component Interaction Summary

| Component | Consumes | Produces | Failure behavior |
|---|---|---|---|
| Feed Adapters | External APIs / files | Normalized `RawEvent` rows | Retry with backoff; stale-data warning after 3 failures; never overwrite cache with partial data |
| Screening Service | RawEvents + watchlist | Match candidates | Deterministic; no external dependency |
| LangGraph Supervisor | AuditorState | Routed agent invocations | Deterministic bypass for unambiguous routes |
| LLM Gateway | Agent prompts | Structured JSON responses | Retry → model fallback → cached response → graceful degradation to review queue |
| Scoring Engine | Classified events + policy.yaml | Score deltas, bands, velocity | Pure function; hot-reloadable policy |
| SSE Broadcaster | Domain events | Push to connected clients | Client reconnect via `EventSource` auto-retry |
| Audit Logger | Every decision (AI + human) | Hash-chained append-only log | Write failure blocks the transaction (audit is not optional) |
| Network Propagator | Resolved risk events + `entity_persons` graph | Indirect-exposure score bumps on related entities | Bounded to 1-hop traversal; cycles impossible by construction |
| Red-Team Agent | Watchlist + sanctions samples | Drill events (`is_drill=true`), detection health report | Drill events are sandboxed — never produce real alerts/SARs |
| Dormancy Detector | Historical mention frequency per entity | Dormancy flags + investigation nudges | Pure statistical check; baseline guard prevents cold-start false flags |

---

## 8. Implementation Status (As-Built)

This section reconciles the design above with the working code, so the document
reflects what the system *does*, not only what it was intended to do. Sections 1–7
describe the target architecture; the notes below record where the current
implementation fully realizes it and the few places it deviates.

### 8.1 Realized as designed

| Area | As-built location | Notes |
|---|---|---|
| Layered structure | `app/api` → `app/services` → `app/repositories` → `app/models` | Client/App/Domain/Storage layers as designed |
| Event-driven ingestion (Loop A) | `app/services/ingestion/` (`base.AdapterRegistry`, `build_scheduler`) | `ProvidedDatasetAdapter`, `SanctionsListAdapter`, `TransactionReplayAdapter`, `InjectAdapter` registered in `app/main.py` lifespan; APScheduler fires each on its own interval, first run at boot |
| Processing pipeline (Loop B) | `app/agents/supervisor.py:run_pipeline` + `poll_unprocessed_events` | LangGraph `StateGraph` over `AuditorState`: monitor → resolver → investigator → reporter with the conditional-edge routing in §5.1 |
| Deterministic scoring | `app/services/scoring/` (`rule_engine`, `bands`, `velocity`, `policy`) | LLM classifies; arithmetic is a pure function over `policy.yaml` |
| Network propagation | `app/services/scoring/propagator.py` | 1-hop over `entity_persons` shared-name graph, `indirect=True`, cycle-safe |
| Hash-chained audit | `app/services/audit_service.py:append_audit` / `verify_chain` | Global genesis-anchored chain; `GET /api/v1/audit/verify` walks every link |
| LLM Gateway + fallback | `app/infrastructure/llm_gateway.py`, `gemini_client.py`, `llm_mock.py` | `build_client()` returns real `GeminiClient` when `GOOGLE_API_KEY`/`GEMINI_API_KEY` is set, else the deterministic mock ladder — no code change to switch |
| Two-stage screening | `app/services/screening.py` | `rapidfuzz.token_set_ratio` pre-filter (threshold 80) against `sanctions_cache`, both forward and reverse (watchlist-addition) directions |
| SSE broadcast | `app/api/sse.py`, `app/infrastructure/broker.py` | `EventSource` stream for `alert.new` / `alert.updated` / `sar.ready` |
| Human-in-the-loop SAR | `app/api/sar.py`, `app/services/sar_service.py` | Versioned edits, approve/reject/request-info, sign-off audited; no auto-file |
| Loop D — self-assessment | `app/services/loop_d.py`, scheduled in `app/main.py` | **Now wired**: an APScheduler interval job (`loop_d_interval_seconds`, default 900s, first run ~20s after boot) runs the red-team drill and dormancy sweep, both writing hash-chained audit entries |
| Red-team detection health | `app/services/red_team_drill.py`, `GET /api/v1/drill/latest` | Deterministic name-evasion variants run through the real screening path; backs the dashboard's DetectionHealth card. The heavier LLM variant generator remains in `demo/red_team.py` as the on-demand path |
| Entity decision graph | `GET /api/v1/entities/{id}/graph` | Built from the entity's `risk_events` (React-Flow node/edge shape) |

### 8.2 Deviations from the design, and why

- **Screening gate is sanctions-based, not generic watchlist-membership.** §5.1 phrases
  the pre-filter as "fuzzy match vs watchlist." In code the resolved entity (and its
  directors) is matched against `sanctions_cache`; an event only advances to the agent
  network on a sanctions/watchlist hit. Pure adverse-media on a non-sanctioned entity is
  screened out at this stage. The demo relies on seeded directors that are guaranteed
  members of the sanctions list (`data/prep/gen_directors.EXACT_MATCH_NAMES`).
- **Gemini model IDs.** §2 names `gemini-3.1-flash-lite`; the client (`gemini_client._MODEL_MAP`)
  maps the gateway's model tags onto currently-available IDs (`gemini-1.5-flash-8b` /
  `gemini-1.5-flash`). Adjust the map when target models change.
- **Vector store scope.** `entity_cards` is populated from the seeded DB by
  `knowledge/index_entities.py`; `event_context` / `regulatory_corpus` are provisioned but
  used opportunistically by the investigator/reporter RAG steps.
- **Loop D cadence.** Designed as nightly/daily; implemented as a configurable interval
  (short by default so the behavior is observable in a demo). Set
  `loop_d_interval_seconds=0` to disable.
- **Decision-replay (UC16)** and **per-person PEP scoring** are not yet backed by dedicated
  tables; the entity graph and audit trail cover the adjacent regulator/auditor use cases.

### 8.3 Runtime prerequisites (see SETUP.md)

The pipeline is only "live" once its data is present: seed entities → directors → account
map → **ChromaDB index of real entities**, and the backend must boot at least once so the
`SanctionsListAdapter` populates `sanctions_cache` (it loads OFAC + OpenSanctions from
`data/sanctions/` on startup). With those in place, an injected adverse-media event for a
watched entity with a sanctioned director flows end-to-end to a live alert and a valid
audit chain.

---

*Prepared as part of the system design phase for Challenge 3 — Continuous KYC Autonomous Auditor. Section 8 records the as-built status of the working prototype.*
