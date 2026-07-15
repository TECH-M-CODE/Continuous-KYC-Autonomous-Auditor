# Sprint 4 — Polish & Pitch (Revised)

**Project:** Continuous KYC Autonomous Auditor (CXKYC) — Tech Mahindra CODE Hackathon, Challenge 3

**Sprint goal:** Zero new features. Clear out the final lingering mock data, then convert a working system into a **winning demo**: every path a judge might poke is hardened, the scenario runs flawlessly three times in a row, the pitch is timed and rehearsed, and there's a fallback for everything that can fail on stage.

**Current Main Branch Status (Entering Condition):** 
* ✅ Agents live on real Gemini
* ✅ SSE streaming and CORS are fixed 
* ✅ Backend AI pipeline is actively scoring events
* ⚠️ **Sprint 1 mock data is still lingering in `entities.py`, `EntityTimeline.jsx`, and `Dashboard.jsx` causing dummy data to render.**

---

## 0. Sprint Structure — three phases, hard boundaries

| Phase | Duration | Rule |
|---|---|---|
| **P1 — Mock Purge & Burn-down** | first ~1.5h | **CRITICAL:** Fix the remaining dummy data issues first. Then triage any bugs from rehearsal #1. Only `demo-blocking` and `judge-visible` bugs get fixed. |
| **P2 — Hardening & polish** | next ~1.5h | The per-dev tracks below. **CODE FREEZE at the end of P2** — after freeze, only config/data/copy changes, no logic merges |
| **P3 — Dry runs & pitch** | final 2h, protected | Full-team. No laptops open on code. Two complete dry runs + pitch timing + Q&A drill |

---

## 1. P1: The Mock Purge (Do this FIRST)
*These tasks must be completed and merged before starting Phase 2.*

**Dev 1 + Dev 3 (Backend Mock Purge):**
- Remove `_MOCK_ENTITIES` from `app/api/entities.py`. Rewrite the `get_entity` and `list_entities` endpoints to query the real SQLite database using the UnitOfWork (`uow.entities.get(...)`).
- Verify `app/api/sars.py` and `app/api/audit.py` are fetching from the real database, not returning static arrays.

**Dev 5 (Frontend Mock Purge):**
- Remove the hardcoded `const entityId = 'entity-1'` from `EntityTimeline.jsx` and ensure it dynamically pulls the entity ID from the route/URL.
- Remove hardcoded numbers (e.g., "Active Alerts 24") from `Dashboard.jsx` and wire them to the real data returned by `apiClient.getAlerts()` and `apiClient.getWatchlist()`.

**Dev 2 + Dev 4 (Data Validation):**
- Look up a real entity ID in the database that has an existing high score (e.g., `C_0060`).
- Inject an Adverse Media event specifically targeted at that entity to cross the 75-point threshold and verify it successfully populates the real Alert Queue on the frontend.

---

## 2. P2: Dev 1 + Dev 3 (paired) — Stress-Test Scoring & Audit Chain

**Why paired:** scoring and audit are the two claims the pitch makes hardest — so they get adversarial testing, not authors-testing-their-own-code. 

### Edge cases to run (checklist)
- Event with **no name candidates** at all → clean `screened_out`, no crash, trace exists
- Entity at score 100 → another critical event → clamps, doesn't overflow; band stays critical
- **Policy hot-reload mid-pipeline** — edit `policy.yaml` while replay-clock runs → next event uses new weights, in-flight event unaffected, no crash
- Same event content injected twice → dedup via `content_hash` → second one never enters the pipeline
- **Force `LLM_MOCK_FAIL_RATE=1.0` with the real key removed** → whole pipeline degrades gracefully: review-queue routing, degraded SAR drafts, amber banners.
- Manually `UPDATE audit_log SET detail=...` on a middle row via sqlite3 → verify button goes red with correct `first_bad_seq` — **screenshot this; it's a pitch slide**
- Reject a SAR with empty notes → validation error, not a 500

---

## 3. P2: Dev 2 — Rehearse ×3, Own the Pitch Runbook

**Dev 2 is demo director from here on** — has interrupt rights on everyone, owns the clock.

### Tasks
1. **Three full rehearsals of `money_laundering` + `false_positive`, from `--reset`, on the demo machine.** 
2. **Write the runbook (one page, printed):** Exact command sequence, exact click sequence, who says what at each `pause` gate.
3. **Record a backup screen capture of one perfect run** (P2, after freeze) — if the live demo dies on stage, narrate over the recording.
4. **Pitch structure (draft with whole team):**
   - 0:00–1:00 problem: periodic KYC review is a snapshot; risk is a stream
   - 1:00–5:00 live demo (scenario 1, pause-gated)
   - 5:00–6:30 the differentiator: false-positive scenario + counterfactual graph 
   - 6:30–7:30 architecture slide: deterministic core, LLM only at three semantic points, degradation ladder, hash chain (tamper screenshot here)
   - 7:30+ Q&A 

---

## 4. P2: Dev 4 — Harden Adapter Failure Paths

### Tasks (checklist)
- **Kill the sanctions source mid-run** (rename the file) → adapter retries with backoff → after 3 failures, `system.health` warning fires → dashboard shows stale-data banner. **Restore file → warning self-clears.** 
- Malformed row in the parquet/CSV → skipped + logged, adapter continues.
- Loop B backlog: inject 30 events at once → queue drains in order, UI stays responsive.
- Startup with **no network at all** → app boots, provided-dataset adapters work, only external-fetch adapters warn.
- Sweep all logs for stack traces during a full scenario run → each one either fixed or downgraded to a handled warning.

---

## 5. P2: Dev 5 — UX Polish + SSE Disconnect Fallback

### Tasks
1. **SSE disconnect fallback:**
   - Amber status dot + "reconnecting" on drop; on reconnect, blanket-invalidate active React Query keys.
   - Test by killing uvicorn mid-scenario and restarting: UI recovers without a manual refresh.
2. **Demo-visibility pass:**
   - Font sizes/contrast readable from 3 meters at 125% zoom.
   - New-alert arrival gets a brief highlight animation.
   - Empty states for every page (e.g., "Watchlist quiet — no active alerts").
3. **DecisionGraph final pass:** initial zoom-to-fit on open; node labels never truncated.
4. **Kill the console noise:** zero React warnings/errors in devtools during a full scenario.
5. **Micro-copy pass:** every banner, toast, and empty state reads like a compliance product.

---

## 6. Failure Playbook (whole team, printed with runbook)

| Failure on stage | Response |
|---|---|
| Gemini quota/key dies | `LLM_MOCK_FAIL_RATE` env routes to mock fallback rung → narrate it as a feature: "you're watching the degradation ladder we designed." |
| Venue Wi-Fi dies | Everything is local (SQLite, ChromaDB). Only live Gemini needs network → same degraded-mode narration. |
| App crashes outright | Backup terminal: restart + `--reset` ≤ 30s while co-presenter talks architecture slide. If second crash → switch to recorded run. |
| Scenario timing runs long | Pause gates mean presenter controls the clock. Skip the false-positive scenario if desperate — never skip the SAR approve beat. |
