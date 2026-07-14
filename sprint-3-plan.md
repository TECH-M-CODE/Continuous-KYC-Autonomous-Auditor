# Sprint 3 — Agents & Scenarios (Day 2, Morning ≈ 4–5 hours)

**Project:** Continuous KYC Autonomous Auditor (CXKYC) — Tech Mahindra CODE Hackathon, Challenge 3

**Sprint goal:** The AI comes alive. By end of sprint: the LangGraph agent network (Monitor → Resolver → Investigator → Reporter) replaces the deterministic `traced_pipeline` skeleton, **real Gemini calls flow through the LLM Gateway** (with the mock kept as fallback), critical alerts trigger async investigation and citation-grounded SAR drafts, every decision lands in a hash-chained audit log, the demo scenario replays on command, and every dashboard screen runs on real data end-to-end.

**Entering condition (from Sprint 2):** engines pure and tested, `traced_pipeline()` runs events end-to-end deterministically, adapters ingesting on schedule, structuring detector live, DecisionGraph rendering real traces, confidence combiner has the `llm_verdict_confidence` seam, evidence/breakdown dict keys agreed.

---

## 0. New Folders & Files This Sprint

```
app/
├── agents/                          # Dev 1
│   ├── __init__.py
│   ├── state.py                     # AuditorState TypedDict
│   ├── supervisor.py                # LangGraph graph + conditional edges
│   ├── monitor.py                   # screening + intake node
│   ├── resolver.py                  # entity disambiguation (LLM)
│   ├── investigator.py              # evidence bundle compiler (LLM, async)
│   ├── reporter.py                  # SAR narrative generator (LLM + RAG)
│   └── prompts/
│       ├── resolver.txt             # disambiguation prompt template
│       ├── classifier.txt           # event type + severity
│       ├── investigator.txt
│       └── reporter.txt
│
├── services/
│   ├── audit_service.py             # Dev 3 — hash-chaining
│   ├── sar_service.py               # Dev 3 — SAR generation + versioning
│   └── ingestion/detectors/         # Dev 4 finishes
│       ├── rapid_movement.py        # stub → real
│       └── high_risk_corridor.py    # stub → real
│
demo/                                # Dev 2
├── __init__.py
├── scenario_engine.py               # scripted, timed event injection
├── scenarios/
│   ├── money_laundering.py          # THE demo: media hit → txn spike → SAR
│   ├── false_positive.py            # same-name trap → dismissal + counterfactual
│   └── sanctions_update.py          # list refresh → reverse-screen hit
├── red_team.py                      # sequence 6.4 (stretch)
└── dormancy.py                      # sequence 6.5 (stretch)
│
frontend/src/
├── pages/SARReview.jsx              # Dev 5 — goes fully live
├── components/
│   ├── EvidenceBundle.jsx
│   ├── ChainVerifyBadge.jsx
│   └── DetectionHealth.jsx          # red-team metric card (stretch)
```

**LLM goes live this sprint:** `GEMINI_API_KEY` set in `.env`, `llm_gateway.py` switches primary from mock to real `gemini-3.1-flash-lite`. **Keep the mock registered as the final fallback rung** — a quota blip mid-demo then degrades to canned-but-sane behavior instead of dying. Verify the key works at Hour 0 before anything else (2-minute smoke test — do not discover a dead key at Hour 3).

---

## 1. Shared Kickoff (Hour 0 → 0:30): Freeze AuditorState + Prompt Output Schemas

Same discipline, third time: **Dev 1 leads a 30-minute whole-team review** of two things everyone touches:

**`agents/state.py` — AuditorState** (the LangGraph shared state):

```python
class AuditorState(TypedDict):
    event: RawEvent
    screen_candidates: list[ScreenCandidate]      # from Monitor
    resolved_entity_id: str | None                # from Resolver
    resolution_confidence: float | None
    resolution_reasoning: str | None
    classification: EventClassification | None    # {event_type, severity}
    score_result: ScoreResult | None              # from scoring engine
    alert_id: str | None
    sar_id: str | None
    trace: TraceBuilder                           # woven through every node
    route: Literal["dismiss", "review", "proceed", "investigate",
                   "report", "done"] | None
    degraded: bool                                # LLM gateway health flag
```

**Prompt output schemas** — the Pydantic models every LLM call must validate against (already half-exist from Sprint 1's mock): `ResolverVerdict {match, confidence, reasoning}`, `EventClassification {event_type, severity}`, `EvidenceBundle {items: [{source, snippet, relevance}]}`, `SARNarrative {narrative, regulatory_basis: [{citation, passage}]}`. Gateway already validates — this meeting just confirms field names match what Devs 3, 4, 5 consume downstream.

---

## 2. Dev 1 — LangGraph Agent Network (supervisor + 4 agents)

**Folder owned:** `app/agents/`

**Design rule to enforce everywhere (from the design principles):** deterministic bypass — the LLM is invoked only where semantic judgment is genuinely needed (disambiguation, severity classification, narratives). Routing decisions with unambiguous inputs are conditional edges on plain values, never LLM calls. Judges will ask "where exactly does the LLM decide things?" — the answer must be "three places, and never the arithmetic."

### Tasks (in order)

1. **`state.py`** — as frozen at kickoff. `TraceBuilder` rides inside the state so every agent node appends trace nodes exactly like `traced_pipeline` did — the DecisionGraph keeps working unchanged.
2. **`monitor.py`** — thin node: wraps Sprint 2's `screening.py`. No LLM. Emits `screen_candidates`; empty → `route="dismiss"` (audit `screened_out`) via conditional edge.
3. **`resolver.py`** — the first real LLM call:
   - `knowledge.retriever.retrieve_entity_candidates(event_text, k=3)` → render candidates + event into `prompts/resolver.txt` → `gateway.complete(prompt, schema=ResolverVerdict, task_tag="resolver_verdict")`
   - Blend with Dev 2's Sprint 2 seam: `confidence.compute_confidence(..., llm_verdict_confidence=verdict.confidence, degraded=result.degraded)` — **one call-site change, exactly as designed**
   - Gateway `degraded=True` → deterministic confidence with the 0.74 ceiling kicks in automatically → routes to human review, never auto-proceeds
4. **`supervisor.py`** — the graph:
   - Nodes: monitor → resolver → classify → score → (investigate) → (report)
   - Conditional edges implement activity diagram 5.1 exactly: confidence <0.40 → dismiss (+ counterfactual via Dev 3's module); 0.40–0.75 → review queue; >0.75 → classify
   - `classify` node = second LLM call (`prompts/classifier.txt`, `EventClassification` schema)
   - `score` node = **pure delegation** to Sprint 2's rule engine + velocity + bands + propagator — zero LLM, copy the `traced_pipeline` wiring
   - Band edges: medium → create alert → done; high → create alert + `route="investigate"`; critical → alert + investigate + `route="report"`
   - Investigator dispatch is **async** (`asyncio.create_task` / background) per sequence 6.2 — the pipeline must not block on evidence compilation; alert broadcasts immediately, `alert.updated` follows when evidence lands
5. **`investigator.py`** — third LLM call:
   - Gather: historical `risk_events` for entity, related entities via `entity_persons`, `event_context` snippets from ChromaDB → compile via `prompts/investigator.txt` → `EvidenceBundle`
   - Attach evidence to alert row, publish `alert.updated`, append audit
   - Also handles re-dispatch with an officer question (the "request more info" branch of activity 5.2) — accept an optional `question` param; **Dev 4 exposes this as `POST /api/sar/{id}/request-info`**
6. **`reporter.py`** — fourth LLM call, RAG-grounded:
   - Calls Dev 3's `sar_service.generate(alert_id)` (Dev 3 owns SAR logic; Reporter is the orchestration node) — division agreed at Hour 0:30: **Dev 1 owns the node + prompt plumbing, Dev 3 owns retrieval + persistence + versioning**
7. **Swap the spine:** Loop B's worker now invokes `supervisor.run(AuditorState(event=...))` instead of `traced_pipeline`. Keep `traced_pipeline` in the tree as the fallback if LangGraph misbehaves late (one-line revert).
8. **Tests** — graph-level with mocked gateway: high-confidence path creates alert + trace with resolve/classify nodes; low confidence dismisses with counterfactual; mid lands review queue; critical spawns investigate + report; `degraded=True` forces review path.

### Definition of done
- A real injected adverse-media event traverses the live graph with **real Gemini calls**, produces an alert with an LLM-written resolution reasoning in the trace, and the DecisionGraph renders it with zero frontend changes

### Dependencies: Resolver consumes Dev 3's retriever (exists) and Dev 2's confidence seam (exists) — both Sprint 2 deliverables. SAR node needs Dev 3's `sar_service` interface by ~Hour 2 (stub `generate()` returning a fixed draft until then).

---

## 3. Dev 2 — Demo Gold (scenario engine + rehearsal scripts; red-team & dormancy as stretch)

**Folder owned:** `demo/`

**Why this is a full track and not an afterthought:** the demo IS the deliverable at a hackathon. The scenario engine turns "hope the pipeline does something interesting" into a scripted, timed, repeatable performance. Dev 2 also becomes the team's first true end-to-end user — the bugs Dev 2 finds at Hour 2 are the ones judges would have found at Hour 26.

### Tasks (in order)

1. **`scenario_engine.py`:**
   - `Scenario = list[Step]`, `Step = {at_seconds, action, payload, narration}` — `narration` is the presenter's cue line, printed to console as each step fires (your co-presenter reads the console)
   - Actions: `inject_event` (via InjectAdapter), `start_txn_replay(entity, speed)`, `refresh_sanctions(with_planted_addition)`, `pause(await_keypress)` — pause steps let the presenter talk over the dashboard before triggering the next beat
   - `python -m demo.run money_laundering` CLI; `--reset` flag that restores DB to a clean seeded snapshot first (copy a pristine `cxkyc.db` file — **make this snapshot at Hour 0 and after every schema change**)
2. **`scenarios/money_laundering.py` — THE demo (the "strongest visual moment"):**
   - t=0: narration "watchlist is quiet" — dashboard idle
   - t=10s: inject adverse-media event ("regulator opens fraud probe into <watched entity>") → live alert appears, band high, click "Why?" → LLM reasoning visible in the graph
   - t=40s: start SAML-D replay-clock pinned to the same entity's mapped accounts → structuring detector fires → transaction_anomaly interleaves on the SAME timeline as the media event → velocity multiplier promotes band → **critical**
   - t=~90s: Investigator evidence lands (`alert.updated`), `sar.ready` fires → SAR draft with GDPR citations opens → presenter edits one sentence, approves → audit trail shows the human sign-off chained after the AI entries
   - Total runtime target: **under 4 minutes**, pause-gated
3. **`scenarios/false_positive.py`:** inject an event about the **same-name-different-person trap** (planted by `gen_directors.py` in Sprint 2) → Resolver confidence lands <0.40 → dismissal with counterfactual → presenter shows the DecisionGraph explaining WHY it declined to alert. This is the differentiator scenario — every team shows alerts firing; almost nobody shows the system correctly *not* firing.
4. **`scenarios/sanctions_update.py`:** trigger the SanctionsListAdapter with a planted addition matching a watched entity's director → reverse-screening hit → alert. Proves the "any signal = an adapter" story live.
5. **Rehearse ×2 by end of sprint** (full ×3 happens in Sprint 4) — file bugs against owners immediately; Dev 2 has interrupt rights on anyone whose component breaks a scenario.
6. **Stretch A — `red_team.py` (sequence 6.4), only after all 3 scenarios pass twice:**
   - Sample watched entities + sanctioned names → one LLM call generates evasion variants (transliterations, typo-squats, shell names, split identities) → inject all with `is_drill=True` → **verify the drill flag propagates: drill events traverse the real pipeline but are hard-blocked from creating real alerts/SARs** (assert this in a test before running it — a drill leaking real alerts mid-demo is a disaster) → compare outcomes vs expected per variant class → write drill report ("17/20 caught") → `GET /api/drill/latest` for Dev 5's DetectionHealth card
7. **Stretch B — `dormancy.py` (sequence 6.5):** pure statistical check per activity diagram — trailing-90-day baseline vs 14-day window, `baseline ≥ 2/week` cold-start guard, raises flag + low-priority nudge, **never touches score**. Self-contained, ~45 min, do only if red-team is done or descoped.

### Definition of done
- All three scenarios run clean from `--reset` twice in a row, under time, with narration cues firing

### Dependencies: needs the live agent graph (Dev 1, ~Hour 2) for full runs — until then, build and dry-run the engine against Sprint 2's `traced_pipeline` spine, which still works.

---

## 4. Dev 3 — Audit Hash-Chaining + SAR Generation (RAG)

**Files owned:** `app/services/audit_service.py`, `app/services/sar_service.py`, `knowledge/` (finish regulatory indexing)

### Tasks (in order)

1. **`audit_service.py` — the tamper-evident chain (do this first, everything writes through it):**
   - `append(actor, action, detail, uow) -> AuditEntry`: `entry_hash = sha256(prev_hash + canonical_json(seq, actor, action, detail, created_at))` — **canonical JSON (sorted keys, no whitespace) or verification breaks on re-serialization**
   - Chain head: genesis entry with `prev_hash = "0"×64` written at DB creation
   - **Write failure blocks the transaction** — non-negotiable per the component table: `append()` runs inside the caller's UnitOfWork; if the audit insert fails, the whole business transaction rolls back. No `try/except-and-continue` anywhere near this.
   - Serialize appends (single asyncio lock) — hash-chaining is inherently sequential; a race here corrupts the chain silently
   - `verify_chain(uow) -> {valid, checked, first_bad_seq}` — walk and re-hash; expose as `GET /api/audit/verify` (route to Dev 4) → powers the dashboard "verify chain" button (UC8)
   - **Migration task:** grep every place Sprints 1–2 wrote audit rows directly via `audit_repo` and route them through `append()` — do this sweep with Dev 4 (30 min, Hour 1)
2. **Finish regulatory indexing:** run `prep_regulatory.py` output fully into the `regulatory_corpus` collection (GDPR articles + PrivacyQA pairs, metadata-tagged). Make `retrieve_regulatory(query, k=4)` real (it was stubbed in Sprint 2). Smoke test: query "record keeping obligations for suspicious activity" → returns GDPR Art. 30-adjacent chunks with article metadata.
3. **`sar_service.py`:**
   - `generate(alert_id, uow) -> SARDraft`: fetch alert + evidence bundle + entity profile → `retrieve_regulatory()` for passages relevant to the typology → render `prompts/reporter.txt` (co-own the prompt with Dev 1) → `gateway.complete(schema=SARNarrative)` → persist `sar_draft` v1 `pending_review` → publish `sar.ready` → audit
   - **Citation integrity check:** every citation in the LLM output must reference a passage actually retrieved — drop any hallucinated citations and log them. This one guard is the difference between "regulation-grounded" and "LLM said so" when a judge cross-examines a citation.
   - Degraded gateway → skeleton SAR from a template (alert facts + retrieved passages, no LLM prose) flagged `degraded_draft=True` — a reviewable draft always exists
   - `save_edit(sar_id, narrative, officer) -> v(n+1)` preserving previous version (activity 5.2's edit loop); `approve/reject(sar_id, officer, notes)` → status + calibration-metric row + audit **as human actor**
4. **Tests** — chain verifies on 50 mixed AI/human entries; tampering with row 20's detail makes `verify_chain` report `first_bad_seq=20`; audit insert failure rolls back the business write; hallucinated citation is stripped; SAR edit produces v2 with v1 intact.

### Definition of done
- Full critical-path run produces a SAR whose every citation resolves to a real retrieved passage; tamper test caught; every write path in the codebase goes through `append()`

### Dependencies: Reporter node split with Dev 1 (agreed Hour 0:30); audit-sweep pairing with Dev 4 at Hour 1.

---

## 5. Dev 4 — API Wiring (mocks → real services) + finish detectors

**Folders owned:** `app/api/`, `app/services/ingestion/detectors/`

**Priority note from the roadmap:** rules first — structuring (done), rapid-movement, high-risk-corridor — **then RF model only if time permits.** The RF model is the first thing to cut; the rules are demo-guaranteed.

### Tasks (in order)

1. **Swap hardcoded controllers for real services, endpoint by endpoint, keeping Sprint 1's shape tests green after each swap** (they're the safety net — a swap that breaks a shape test breaks Dev 5):
   - `GET /api/alerts`, `/api/alerts/{id}` → alert_repo (+ trace join)
   - `POST /api/alerts/{id}/dismiss|escalate` → real status change + `audit_service.append` as human actor + `alert.updated` broadcast
   - `GET /api/entities/{id}` → real profile + real interleaved timeline from `risk_events`
   - `GET /api/sar`, `/{id}` + `POST approve|reject|edit` → `sar_service` calls
   - **New:** `POST /api/sar/{id}/request-info` → Investigator re-dispatch with officer question (Dev 1's node handles it)
   - `GET /api/audit` → real entries; **new** `GET /api/audit/verify` → `verify_chain()`
   - `GET /api/watchlist` + `POST` → real entity updates (+ re-index the entity card in ChromaDB on change — one-line call to Dev 3's indexer)
   - **New (stretch-serving):** `GET /api/drill/latest` returning latest drill report or 404
2. **Audit sweep with Dev 3 (Hour 1, 30 min):** route all direct `audit_repo` writes in api/ and ingestion/ through `audit_service.append()`.
3. **Finish `rapid_movement.py`:** in→out flow through an account within N hours above threshold ratio → evidence `{in_txns, out_txns, window_hours, net_flow}` (keys per the Sprint 2 agreement with Dev 3's narrator).
4. **Finish `high_risk_corridor.py`:** sender/receiver country pair where either is FATF-listed (list from policy.yaml — single source of truth) + amount percentile guard → evidence `{corridor, txn_count, total_amount}`.
5. **Wire Loop B to the supervisor** (with Dev 1, ~Hour 2): worker pulls unprocessed events → `supervisor.run()`; confirm concurrency is sane (process events sequentially or small semaphore — SQLite writes + LLM rate limits both argue against wide parallelism).
6. **Stretch — RF model (only if Hours 3.5+ are calm):** engineered per-account features (txn frequency, amount percentiles, cross-border ratio, unique counterparties, burst detection) on the parquet sample, `RandomForestClassifier`, emit as a fourth detector with `typology="model_flagged"` and feature importances as evidence. **If skipped, say so proudly in the pitch:** "we chose explainable rules over a black-box model — the model slot exists in the architecture."

### Definition of done
- Zero hardcoded JSON remains; all shape tests green; all three rule detectors fire on the parquet sample; dismiss/escalate/approve from the UI produce chained audit entries as human actor

### Dependencies: `sar_service`/`audit_service` interfaces from Dev 3 (Hour 1–2); supervisor wiring with Dev 1 (Hour 2).

---

## 6. Dev 5 — SAR Review Live + Full Real-Data Dashboard

**Folder owned:** `frontend/`

### Tasks (in order)

1. **`sar.ready` + `alert.updated` SSE handling:** extend `useSSE` event map → React Query invalidations (`['sars']`, `['alerts', id]`). `sar.ready` → toast with "Review now" deep link. `alert.updated` on an open alert → evidence section refreshes in place (the judge watches evidence "arrive" seconds after the alert — deliberately visible async).
2. **SARReview goes fully live (the big page this sprint):**
   - Load real draft; narrative editable; **Save** → `POST /edit` → version bump visible ("v2 — edited by you, v1 preserved" with a version dropdown to view priors)
   - `regulatory_basis` rendered as citation chips; click → drawer with the retrieved passage text (this is the "grounded, not generated" proof judges can poke)
   - **Approve** (confirm dialog + sign-off note field) / **Reject** (required notes) → status banner; **Request more info** → question input → `POST /request-info` → "Investigator dispatched" pending state → evidence refresh on `alert.updated`
   - `degraded_draft=True` → amber banner: "Draft generated in degraded mode — template + retrieved passages, review carefully"
3. **`EvidenceBundle.jsx`:** evidence items as cards `{source, snippet, relevance}` sorted by relevance, used in both AlertQueue detail and SARReview.
4. **`ChainVerifyBadge.jsx`:** "Verify chain" button → `GET /api/audit/verify` → green "Chain intact — N entries verified" or red with `first_bad_seq`. Simple, and it's UC8's entire UI.
5. **Human actions close the loop visually:** after dismiss/escalate/approve, optimistically show the new audit entry appearing at the top of a mini audit feed on the same screen — the human-in-the-loop story made visible without navigating away.
6. **SSE disconnect handling (starts here, polished Sprint 4):** status dot amber on disconnect + "reconnecting…"; on reconnect, blanket-invalidate active queries so nothing is stale.
7. **Stretch — `DetectionHealth.jsx`:** card on Admin page reading `/api/drill/latest` — "17/20 evasion variants caught" with per-class misses. Build only if Dev 2's red-team stretch lands.

### Definition of done
- Full officer journey clickable end-to-end on real data: alert arrives → investigate → evidence arrives live → SAR ready toast → edit (v2) → approve → audit entry appears → chain verifies green

### Dependencies: Dev 4's endpoint swaps land progressively — work in the same order Dev 4 swaps (alerts → SAR → audit) to stay unblocked.

---

## 7. Timeline & Sync Points

| Hour | Milestone |
|---|---|
| 0:00–0:30 | Whole-team: AuditorState + prompt schemas frozen · Reporter/sar_service split agreed (Dev 1/Dev 3) · **Gemini key smoke-tested** · Dev 2 snapshots clean DB |
| 1:00 | Dev 3 + Dev 4: audit-sweep pairing (30 min) · Dev 3 ships `audit_service` interface |
| 2:00 | Dev 1's graph runs end-to-end with live LLM → Dev 4 wires Loop B to supervisor · Dev 3 ships `sar_service.generate` → Reporter node goes real · Dev 2 switches scenarios from `traced_pipeline` to live graph |
| 3:00 | Dev 4's endpoint swaps complete · Dev 5's SAR journey live · Dev 2 first full money_laundering run on the real stack — bugs filed |
| 3:30 | Stretch gate: all 3 scenarios pass? → Dev 2 starts red-team; Dev 4 considers RF; else all hands on scenario bugs |
| 4:00–4:30 | **Integration checkpoint = demo dress rehearsal #1:** `python -m demo.run money_laundering --reset` in front of the whole team, then `false_positive`, then chain-verify click. Every failure gets an owner and goes top of Sprint 4's fix list. |

## 8. Cut order if time runs short (pre-agreed, no debate at Hour 3)
1. RF model (rules carry the demo)
2. Dormancy detector
3. Red-team agent (keep UC12 in the pitch as "designed, sequence diagram 6.4" — the sandboxing design is still a talking point)
4. `sanctions_update.py` scenario (mention verbally instead)
**Never cut:** audit chaining, citation integrity check, the false-positive scenario, degraded-mode paths.

## 9. Sprint 4 preview (Day 2 PM — polish & pitch)
No new features. Dev 1+3 stress-test scoring/audit edge cases (empty evidence, concurrent appends, policy reload mid-pipeline); Dev 2 rehearses ×3 and times the pitch; Dev 4 hardens adapter failure paths (stale-data warnings, retry backoff — judges may probe these); Dev 5 UX polish + SSE-disconnect fallback finished. Everyone frees the final 2 hours for the full dry run.
