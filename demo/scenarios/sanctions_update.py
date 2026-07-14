"""Sanctions list refresh → reverse-screening hit.

Triggers the SanctionsListAdapter with a planted addition matching a watched
entity's director. The refresh reverse-screens the existing book and raises an
alert with no new transaction or media event. Proves the "any signal = an
adapter" story live.
"""

from __future__ import annotations

from demo.types import Action, Scenario, Step

#: A director of a watched entity. The planted sanctions addition names them,
#: so the refresh reverse-screens and hits.
WATCHED_DIRECTOR = "Elena Kovač"
PLANTED_ADDITION = {
    "name": WATCHED_DIRECTOR,
    "list": "OFAC-SDN",
    "program": "GLOMAG",
    "reason": "designation for corruption-related activity",
}


def build() -> Scenario:
    return Scenario(
        name="sanctions_update",
        title="Sanctions Update — the list changes, the book re-screens itself",
        description=(
            "A sanctions refresh adds a name matching a watched entity's director. "
            "Reverse-screening fires an alert with no new transaction or media "
            "event — the trigger is the list itself."),
        budget_seconds=90.0,
        steps=[
            Step(0, Action.PAUSE,
                 "Screening isn't only forward-looking. When a sanctions list "
                 "changes, everyone you already monitor must be re-checked against "
                 "the new entries. Watch a list refresh reach back into the book.",
                 {"message": "explain reverse-screening before the refresh", "seconds": 6}),
            Step(10, Action.REFRESH_SANCTIONS,
                 f"The list just updated. One of the new designations names "
                 f"{WATCHED_DIRECTOR} — a director of an entity we already watch.",
                 {"planted_addition": PLANTED_ADDITION}),
            Step(24, Action.ASSERT_STATE,
                 "[rehearsal] reverse-screen produced an alert",
                 {"entity": WATCHED_DIRECTOR, "min_alerts": 1}),
            Step(26, Action.PAUSE,
                 "No transaction, no news — the refresh alone triggered it. The "
                 "adapter reverse-screened the existing book, matched the director, "
                 "and raised the alert. Every signal is just an adapter; the pipeline "
                 "downstream is identical.",
                 {"message": "show the alert → source = sanctions refresh", "seconds": 10}),
        ],
    )


def verify(watchlist_directors: list[str]) -> list[str]:
    if WATCHED_DIRECTOR not in watchlist_directors:
        return [
            f"{WATCHED_DIRECTOR!r} is not a director of any watched entity — the "
            f"planted addition won't reverse-screen to anything. Check the seed."
        ]
    return []