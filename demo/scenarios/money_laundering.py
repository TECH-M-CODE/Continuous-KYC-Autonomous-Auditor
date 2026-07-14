"""THE demo: adverse media hit → transaction spike → critical → SAR.

Two independent signals (news + transaction pattern) interleave on the SAME
entity timeline; the velocity multiplier promotes the band to critical; the
Investigator's evidence lands visibly late (deliberate async); the SAR draft
opens with citations that resolve to real retrieved passages.

Budget is *scripted* time (240s); stage time is longer because the presenter
talks over the pauses.
"""

from __future__ import annotations

from demo.types import Action, Scenario, Step

#: Must match a seeded watchlist entity with mapped SAML-D accounts.
WATCHED_ENTITY = "Meridian Holdings Ltd"


def build() -> Scenario:
    return Scenario(
        name="money_laundering",
        title="Money Laundering — media hit meets transaction spike",
        description=(
            "Two independent signals converge on one entity. Band escalates to "
            "critical, evidence compiles asynchronously, SAR drafts with real "
            "regulatory citations, officer signs off, chain verifies."),
        budget_seconds=240.0,
        steps=[
            Step(0, Action.PAUSE,
                 "The watchlist is quiet. Twelve entities under continuous "
                 "monitoring, no open alerts. The system is watching, not waiting "
                 "to be asked.",
                 {"message": "dashboard idle — set the scene, then trigger", "seconds": 5}),
            Step(10, Action.INJECT_EVENT,
                 "A regulator opens a fraud probe. That story just hit the wire — "
                 "and the system has already screened it against the watchlist.",
                 {"event_type": "adverse_media", "entity_name": WATCHED_ENTITY,
                  "source": "reuters_feed",
                  "text": (f"Financial regulator opens formal fraud investigation into "
                           f"{WATCHED_ENTITY}, citing irregularities in cross-border "
                           f"settlement flows. The probe follows a supervisory review "
                           f"of the firm's correspondent banking relationships.")}),
            Step(25, Action.ASSERT_STATE,
                 "[rehearsal] alert exists, band is high",
                 {"entity": WATCHED_ENTITY, "min_alerts": 1, "band": "high"}),
            Step(26, Action.PAUSE,
                 "Alert is live. Band: HIGH. Click 'Why?' — this is the decision "
                 "graph. Screening matched, the Resolver disambiguated to this "
                 "entity, and here is the model's own reasoning. Nothing is a black box.",
                 {"message": "open the alert → 'Why?' → walk the DecisionGraph", "seconds": 8}),
            Step(40, Action.START_TXN_REPLAY,
                 "Now watch the accounts. Same entity — the transaction replay is "
                 "pinned to its mapped accounts, running at 60x.",
                 {"entity": WATCHED_ENTITY, "speed": 60.0, "pattern": "structuring"}),
            Step(62, Action.ASSERT_STATE,
                 "[rehearsal] band promoted to critical",
                 {"entity": WATCHED_ENTITY, "band": "critical"}),
            Step(70, Action.PAUSE,
                 "The structuring detector fired — deposits just under the reporting "
                 "threshold. And the entity timeline shows the news event and the "
                 "transaction anomaly on the SAME timeline, minutes apart. The "
                 "velocity multiplier promoted the band. We are now CRITICAL.",
                 {"message": "show interleaved timeline → band promotion", "seconds": 10}),
            Step(90, Action.PAUSE,
                 "Evidence just arrived — after the alert. The Investigator runs "
                 "asynchronously; we never block an alert on evidence compilation. "
                 "And the SAR is ready.",
                 {"message": "alert.updated → evidence cards → sar.ready toast", "seconds": 10}),
            Step(100, Action.ASSERT_STATE,
                 "[rehearsal] SAR draft exists",
                 {"entity": WATCHED_ENTITY, "min_sars": 1}),
            Step(105, Action.PAUSE,
                 "Here is the draft. These citation chips are not decoration — click "
                 "one and you get the actual retrieved passage. Every citation "
                 "resolves to a passage the system genuinely retrieved; anything the "
                 "model invented was stripped before you saw it. I'll edit one "
                 "sentence — and approve.",
                 {"message": "click a citation chip → edit → save (v2) → approve", "seconds": 15}),
            Step(125, Action.PAUSE,
                 "The audit trail. Every AI decision hash-chained. My sign-off chained "
                 "right after as a human actor. Click 'Verify chain' — green. Tamper "
                 "with any entry and that button turns red and names the row.",
                 {"message": "audit trail → ChainVerifyBadge → green", "seconds": 12}),
            Step(140, Action.STOP_TXN_REPLAY,
                 "Scenario complete. Replay clock stopped.",
                 {"entity": WATCHED_ENTITY}),
        ],
    )


def verify(watchlist: list[str], mapped_accounts: dict[str, list[str]]) -> list[str]:
    """Pre-flight. Catching a missing entity here costs 200ms; at t=40 it costs
    the demo."""
    problems: list[str] = []
    if WATCHED_ENTITY not in watchlist:
        problems.append(
            f"{WATCHED_ENTITY!r} not on the seeded watchlist — screening will "
            f"dismiss the media event and no alert appears")
    if not mapped_accounts.get(WATCHED_ENTITY):
        problems.append(
            f"{WATCHED_ENTITY!r} has no mapped SAML-D accounts — the txn replay pins "
            f"to nothing and the band never promotes to critical")
    return problems