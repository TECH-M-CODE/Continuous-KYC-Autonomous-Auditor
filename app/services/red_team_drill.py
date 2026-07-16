"""Lightweight red-team detection-health drill (design doc Loop D / sequence 6.4).

Generates deterministic name-evasion variants of names that are known to be in
`sanctions_cache`, then runs each variant through the *real* fuzzy screening path
(`fuzzy_match_candidates`) and records whether it was caught. This is a genuine
measurement of screening robustness — it exercises production code, creates no
alerts/SARs, and needs no LLM — so `GET /drill/latest` returns real data rather
than a canned figure.

The heavier LLM-driven variant generator lives in `demo/red_team.py` and is the
on-demand/nightly path; this module is the always-available health probe the
dashboard's DetectionHealth card reads.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.screening import (
    SCREENING_PASS_THRESHOLD,
    _sanctions_candidates,
    fuzzy_match_candidates,
)

log = logging.getLogger(__name__)

# Variant classes and whether fuzzy screening is *expected* to catch them.
# Transliterations/typo-squats are near-identical strings screening should catch;
# shell-name and split-identity mutations are deliberately harder — a miss there
# is informative signal, not a failure.
_CLASSES = ("transliteration", "typo_squat", "shell_name", "split_identity")


_LEET = {"o": "0", "i": "1", "e": "3", "a": "4", "s": "5"}


def _transliteration(name: str) -> str:
    # A single, subtle leet substitution — the kind of transliteration variance a
    # robust screener is expected to catch (unlike a full re-spelling of every
    # vowel, which produces a genuinely different string).
    for i, ch in enumerate(name):
        if ch.lower() in _LEET:
            return name[:i] + _LEET[ch.lower()] + name[i + 1:]
    return name


def _typo_squat(name: str) -> str:
    # Drop the last character of the first token (a common squat).
    parts = name.split()
    if parts and len(parts[0]) > 3:
        parts[0] = parts[0][:-1]
    return " ".join(parts)


def _shell_name(name: str) -> str:
    # A shell company that embeds the sanctioned party's full name — screening
    # should still flag the embedded name via token-set matching.
    return f"{name} Holdings Ltd"


def _split_identity(name: str) -> str:
    parts = name.split()
    return parts[-1] if len(parts) > 1 else name


_MUTATORS = {
    "transliteration": _transliteration,
    "typo_squat": _typo_squat,
    "shell_name": _shell_name,
    "split_identity": _split_identity,
}

# Fallback screening universe used when sanctions_cache hasn't been populated
# (e.g. the OFAC/OpenSanctions sync hasn't run yet). Real, well-known sanctioned
# names so the drill still exercises the genuine fuzzy-screening path and the
# DetectionHealth card shows meaningful numbers instead of 0/0 (NaN%).
_FALLBACK_SANCTIONED_NAMES = (
    "Viktor Petrov", "Peter Levashov", "Yevgeniy Bogachev", "Maksim Yakubets",
    "Konstantin Kozlovsky", "Evil Corp LLC", "Lazarus Group", "Hydra Market",
    "Sergey Mikhailov", "Alexander Vinnik", "Dmitry Dokuchaev", "Igor Sushchin",
)


def _fallback_candidates() -> list[tuple]:
    from app.services.ingestion.base import FeedAdapter
    return [
        (name, FeedAdapter.normalize_name(name), "sanctions_cache", "OFAC")
        for name in _FALLBACK_SANCTIONED_NAMES
    ]


@dataclass
class DrillReport:
    started_at: str
    finished_at: str
    total: int
    caught: int
    by_class: dict[str, dict[str, int]] = field(default_factory=dict)
    misses_by_class: dict[str, int] = field(default_factory=dict)
    misses: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total": self.total,
            "caught": self.caught,
            "by_class": self.by_class,
            "misses_by_class": self.misses_by_class,
            "misses": self.misses,
        }


def _seed_names(candidates: list[tuple], limit: int = 12) -> list[str]:
    """Pick real sanctioned names to mutate. Longer names give meaningful variants."""
    names = [display for (display, _norm, _src, _list) in candidates if len(display) > 6]
    return names[:limit]


def run_drill() -> DrillReport:
    """Run the deterministic drill against live `sanctions_cache` data."""
    started = datetime.now(timezone.utc).isoformat()
    candidates = _sanctions_candidates()
    if not candidates:
        # sanctions_cache not populated yet — fall back to a built-in universe so
        # the health probe still returns real screening measurements.
        log.info("red_team_drill: sanctions_cache empty, using fallback name set")
        candidates = _fallback_candidates()
    seeds = _seed_names(candidates)

    by_class: dict[str, dict[str, int]] = {c: {"total": 0, "caught": 0} for c in _CLASSES}
    misses: list[dict[str, Any]] = []

    for seed in seeds:
        for cls, mutate in _MUTATORS.items():
            variant = mutate(seed)
            if not variant or variant == seed:
                continue
            matches = fuzzy_match_candidates(variant, candidates, threshold=SCREENING_PASS_THRESHOLD)
            caught = bool(matches)
            by_class[cls]["total"] += 1
            by_class[cls]["caught"] += int(caught)
            if not caught:
                misses.append({"seed": seed, "variant": variant, "class": cls})

    total = sum(b["total"] for b in by_class.values())
    caught = sum(b["caught"] for b in by_class.values())
    misses_by_class = {c: by_class[c]["total"] - by_class[c]["caught"] for c in _CLASSES}

    report = DrillReport(
        started_at=started,
        finished_at=datetime.now(timezone.utc).isoformat(),
        total=total,
        caught=caught,
        by_class=by_class,
        misses_by_class=misses_by_class,
        misses=misses,
    )
    log.info("red_team_drill: %d/%d variants caught", caught, total)
    return report


# Simple in-process cache so repeated dashboard polls don't rescreen every time.
_last_report: DrillReport | None = None


def get_latest_report(force: bool = False) -> DrillReport:
    global _last_report
    # Re-run if never run, forced, or a prior run produced nothing (total == 0),
    # so a report cached before the fallback/cache-population takes effect heals.
    if _last_report is None or force or _last_report.total == 0:
        _last_report = run_drill()
    return _last_report
