"""The differentiator: the system correctly does NOT fire.

Injects an event about the same-name-different-person trap planted by
gen_directors.py in Sprint 2. The Resolver lands confidence < 0.40 → dismissal
with a counterfactual → the DecisionGraph explains WHY it declined to alert.

Every team shows alerts firing; almost nobody shows correct non-firing.
"""

from __future__ import annotations

from demo.types import Action, Scenario, Step

#: The innocent namesake — same name as a watched director, different person.
#: Planted by gen_directors.py. The distinguishing facts (DOB, nationality)
#: are what should drive the Resolver below threshold.
DECOY_NAME = "James Whitfield"
DECOY_CONTEXT = "a retired schoolteacher in Leeds with no financial-sector history"


def build() -> Scenario:
    return Scenario(
        name="false_positive",
        title="False Positive — the alert that correctly never fires",
        description=(
            "A same-name-different-person trap. The Resolver disambiguates below "
            "threshold, dismisses with a counterfactual, and the DecisionGraph "
            "shows exactly why. Precision made visible."),
        budget_seconds=120.0,
        steps=[
            Step(0, Action.PAUSE,
                 "Naive name-matching is why compliance teams drown in false "
                 "positives. Watch what happens when a story mentions someone who "
                 "shares a name with a watched director — but isn't them.",
                 {"message": "set up the trap — same name, different person", "seconds": 5}),
            Step(8, Action.INJECT_EVENT,
                 f"An adverse-media story naming {DECOY_NAME}. On the watchlist we "
                 f"have a director with exactly that name. A keyword system alerts "
                 f"here. Watch ours.",
                 {"event_type": "adverse_media", "entity_name": DECOY_NAME,
                  "source": "local_news",
                  "text": (f"{DECOY_NAME}, {DECOY_CONTEXT}, was named in a minor "
                           f"local licensing dispute unrelated to financial services.")}),
            Step(22, Action.ASSERT_STATE,
                 "[rehearsal] no alert fired for the decoy",
                 {"entity": DECOY_NAME, "min_alerts": 0, "band": None}),
            Step(24, Action.PAUSE,
                 "No alert. The Resolver pulled candidates, compared the "
                 "distinguishing facts — occupation, location, history — and landed "
                 "confidence below 0.40. Open the decision graph: it dismissed, and "
                 "it shows the counterfactual — what WOULD have had to be true for "
                 "this to match our director. That is the difference between a system "
                 "that's quiet and a system that's precise.",
                 {"message": "open DecisionGraph → dismissal + counterfactual", "seconds": 12}),
        ],
    )


def verify(watchlist: list[str]) -> list[str]:
    """The decoy name must collide with a real watched entity, or there is no
    trap to disarm and the scenario proves nothing."""
    if DECOY_NAME not in watchlist:
        return [
            f"{DECOY_NAME!r} is not on the watchlist — without the name collision "
            f"there is no false-positive trap to demonstrate. Check gen_directors.py "
            f"planted the namesake."
        ]
    return []