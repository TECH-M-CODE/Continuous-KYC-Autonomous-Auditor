"""
tests/test_verification.py — Dev 2, Sprint 2.

Table-driven, zero mocks needed: every function under test is pure. The only
"fixture" is the policy YAML and a handful of dict RawEvents.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from app.services.verification import verify
from app.services.verification.confidence import compute_confidence, to_band
from app.services.verification.credibility import extract_domain, score_source
from app.services.verification.fact_check import corroborate, normalize_name

POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "policy.verification.yaml"
NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def policy() -> dict:
    return yaml.safe_load(POLICY_PATH.read_text())


def ev(**kw) -> dict:
    base = {
        "event_id": "e-subject",
        "source": "Reuters",
        "url": "https://www.reuters.com/legal/acme-probe",
        "title": "Acme Holdings Ltd under investigation",
        "author": "R. Desk",
        "entity_id": "ent-1",
        "entity_name": "Acme Holdings Ltd",
        "name_candidates": ["Acme Holdings Ltd"],
        "published_at": NOW,
    }
    base.update(kw)
    return base


# --------------------------------------------------------------------------- #
# credibility
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://news.reuters.com/x?y=1", "news.reuters.com"),
        ("https://www.ft.com/a", "ft.com"),
        ("reuters.com", "reuters.com"),
        ("Reuters", None),
        (None, None),
    ],
)
def test_extract_domain(url, expected):
    assert extract_domain(url) == expected


@pytest.mark.parametrize(
    "event,expected_tier,expected_score",
    [
        (ev(source="OFAC", url=None), "official_list", 1.0),                     # source table
        (ev(source="X", url="https://sanctions.treasury.gov/sdn"), "official_list", 1.0),
        (ev(), "major_wire", 0.9),                                               # reuters domain
        (ev(source="The Hindu", url="https://www.thehindu.com/a"), "regional_press", 0.7),
        (ev(source="rss", url="https://someguy.substack.com/p/1", author=None),
         "blog_unknown_rss", 0.35),                                              # 0.40 - 0.05 no author
        (ev(source="Weird Feed", url="https://unheard-of.xyz/a", author=None),
         "unknown", 0.45),                                                       # 0.50 - 0.05
    ],
)
def test_score_source_tiers(policy, event, expected_tier, expected_score):
    r = score_source(event, policy)
    assert r.tier == expected_tier
    assert r.credibility == pytest.approx(expected_score, abs=1e-6)


def test_unknown_source_raises_low_credibility_flag(policy):
    r = score_source(ev(source="Some Blog", url="https://nowhere.example/a"), policy)
    assert r.low_credibility is True
    assert r.breakdown["matched_by"] == "default"


def test_official_list_is_immune_to_heuristics(policy):
    r = score_source(
        ev(source="OFAC", url=None, author=None, title="allegedly sanctioned"), policy
    )
    assert r.credibility == 1.0
    assert r.low_credibility is False


def test_opinion_marker_penalty(policy):
    clean = score_source(ev(), policy).credibility
    rumor = score_source(ev(title="Acme allegedly laundering funds"), policy).credibility
    assert rumor == pytest.approx(clean - 0.10, abs=1e-6)


# --------------------------------------------------------------------------- #
# fact_check / corroboration
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "a,b,same",
    [
        ("Acme Holdings Ltd", "Acme Holdings Limited", True),
        ("Acme Holdings Ltd", "ACME HOLDINGS", True),
        ("Acme Holdings", "Zenith Traders", False),
    ],
)
def test_normalize_name_drops_legal_suffixes(a, b, same):
    assert (normalize_name(a) == normalize_name(b)) is same


def test_zero_corroboration_no_boost(policy):
    r = corroborate(ev(), policy=policy, candidates=[])
    assert r.corroborating_count == 0
    assert r.corroboration_boost == 0.0


def test_one_distinct_source_gives_10(policy):
    others = [
        ev(event_id="e2", source="Bloomberg", url="https://bloomberg.com/a",
           entity_name="Acme Holdings Limited", name_candidates=["Acme Holdings Limited"],
           published_at=NOW + timedelta(hours=5)),
    ]
    r = corroborate(ev(), policy=policy, candidates=others)
    assert r.corroborating_count == 1
    assert r.corroboration_boost == pytest.approx(0.10)


def test_two_plus_sources_saturate_at_20(policy):
    others = [
        ev(event_id="e2", source="Bloomberg", url="https://bloomberg.com/a",
           published_at=NOW + timedelta(hours=5)),
        ev(event_id="e3", source="AP", url="https://apnews.com/a",
           published_at=NOW - timedelta(hours=10)),
        ev(event_id="e4", source="FT", url="https://ft.com/a",
           published_at=NOW + timedelta(hours=20)),
    ]
    r = corroborate(ev(), policy=policy, candidates=others)
    assert r.corroborating_count == 3
    assert r.corroboration_boost == pytest.approx(0.20)   # saturates


def test_same_source_repeats_do_not_corroborate(policy):
    """Syndication guard: 3 more Reuters pieces are still one source."""
    others = [
        ev(event_id=f"e{i}", source="Reuters", url=f"https://reuters.com/{i}",
           published_at=NOW + timedelta(hours=i))
        for i in range(2, 5)
    ]
    r = corroborate(ev(), policy=policy, candidates=others)
    assert r.corroborating_count == 0
    assert r.breakdown["rejected"]["same_source"] == 3


def test_outside_window_is_excluded(policy):
    others = [
        ev(event_id="e2", source="Bloomberg", url="https://bloomberg.com/a",
           published_at=NOW + timedelta(hours=100)),   # > 72h
    ]
    r = corroborate(ev(), policy=policy, candidates=others)
    assert r.corroborating_count == 0
    assert r.breakdown["rejected"]["outside_window"] == 1


def test_different_entity_is_excluded(policy):
    others = [
        ev(event_id="e2", source="Bloomberg", url="https://bloomberg.com/a",
           entity_name="Zenith Traders Pvt", name_candidates=["Zenith Traders Pvt"],
           published_at=NOW + timedelta(hours=2)),
    ]
    r = corroborate(ev(), policy=policy, candidates=others)
    assert r.corroborating_count == 0
    assert r.breakdown["rejected"]["name_below_threshold"] == 1


def test_corroborate_survives_a_dead_uow(policy):
    class Boom:
        events_raw = None
    r = corroborate(ev(), uow=Boom(), policy=policy)
    assert r.corroborating_count == 0     # degrade to no boost, never raise


# --------------------------------------------------------------------------- #
# confidence: bands
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "score,band",
    [
        (0.00, "dismiss"), (0.39, "dismiss"),
        (0.40, "review"), (0.60, "review"), (0.7499, "review"),
        (0.75, "proceed"), (1.00, "proceed"),
    ],
)
def test_to_band_boundaries(policy, score, band):
    assert to_band(score, policy) == band


# --------------------------------------------------------------------------- #
# confidence: the formula
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "match,cred,boost,expected",
    [
        (100, 1.0, 0.00, 1.00),   # perfect sanctions hit
        (95,  0.9, 0.20, 1.00),   # 0.855 + 0.20 = 1.055 -> clamped
        (87,  0.9, 0.10, 0.883),  # 0.783 + 0.10
        (90,  0.4, 0.00, 0.360),  # single blog, uncorroborated
        (64,  0.4, 0.00, 0.256),  # garbage
        (0,   1.0, 0.20, 0.200),  # no name match, boost alone can't save it
    ],
)
def test_deterministic_formula(policy, match, cred, boost, expected):
    r = compute_confidence(match, cred, boost, policy)
    assert r.confidence == pytest.approx(expected, abs=1e-3)


def test_high_credibility_corroborated_proceeds(policy):
    r = compute_confidence(92, 0.9, 0.20, policy)
    assert r.band == "proceed"


def test_single_blog_source_lands_review(policy):
    """Strong name match, weak uncorroborated source -> human, not auto-alert."""
    r = compute_confidence(match_score=100, credibility=0.4, corroboration=0.10, policy=policy)
    assert r.confidence == pytest.approx(0.50)
    assert r.band == "review"


def test_garbage_match_dismisses(policy):
    r = compute_confidence(64, 0.4, 0.0, policy)
    assert r.band == "dismiss"


# --------------------------------------------------------------------------- #
# confidence: degraded ceiling (the fail-safe)
# --------------------------------------------------------------------------- #
def test_degraded_caps_at_review_even_with_perfect_inputs(policy):
    r = compute_confidence(100, 1.0, 0.20, policy, degraded=True)
    assert r.confidence == pytest.approx(0.74)
    assert r.ceiling_applied is True
    assert r.band == "review"                      # never "proceed"
    assert r.breakdown["pre_ceiling_confidence"] == pytest.approx(1.0)


def test_degraded_does_not_inflate_a_low_score(policy):
    r = compute_confidence(64, 0.4, 0.0, policy, degraded=True)
    assert r.confidence == pytest.approx(0.256, abs=1e-3)
    assert r.ceiling_applied is False
    assert r.band == "dismiss"                     # ceiling is a cap, not a floor


# --------------------------------------------------------------------------- #
# confidence: the Sprint 3 seam
# --------------------------------------------------------------------------- #
def test_llm_blend_signature_is_inert_when_absent(policy):
    a = compute_confidence(87, 0.9, 0.10, policy)
    b = compute_confidence(87, 0.9, 0.10, policy, llm_verdict_confidence=None)
    assert a.confidence == b.confidence
    assert a.llm_blended is False


def test_llm_blend_uses_60_40(policy):
    # deterministic = 0.87*0.9 + 0.10 = 0.883 ; llm = 0.93
    # 0.6*0.93 + 0.4*0.883 = 0.5580 + 0.3532 = 0.9112
    r = compute_confidence(87, 0.9, 0.10, policy, llm_verdict_confidence=0.93)
    assert r.confidence == pytest.approx(0.9112, abs=1e-4)
    assert r.llm_blended is True
    assert r.band == "proceed"


def test_llm_blend_still_respects_the_degraded_ceiling(policy):
    r = compute_confidence(100, 1.0, 0.2, policy, llm_verdict_confidence=1.0, degraded=True)
    assert r.confidence == pytest.approx(0.74)
    assert r.band == "review"


# --------------------------------------------------------------------------- #
# breakdown discipline — Dev 3 consumes these keys
# --------------------------------------------------------------------------- #
def test_every_result_carries_a_breakdown(policy):
    out = verify(ev(), match_score=87, policy=policy, candidates=[])
    for required in (
        "match_score", "normalized_match", "credibility", "corroboration_boost",
        "deterministic", "confidence", "band", "degraded", "formula",
    ):
        assert required in out.confidence.breakdown, required
    assert out.credibility.breakdown["tier"] == "major_wire"
    assert "candidates_scanned" in out.corroboration.breakdown


# --------------------------------------------------------------------------- #
# end-to-end facade: fake screened event + seeded events_raw
# --------------------------------------------------------------------------- #
def test_verify_end_to_end_proceeds(policy):
    seeded = [
        ev(event_id="e2", source="Bloomberg", url="https://bloomberg.com/a",
           entity_name="Acme Holdings Limited", published_at=NOW + timedelta(hours=3)),
        ev(event_id="e3", source="AP", url="https://apnews.com/a",
           entity_name="Acme Hldgs Ltd", published_at=NOW - timedelta(hours=8)),
    ]
    out = verify(ev(), match_score=92, policy=policy, candidates=seeded)

    assert out.credibility.tier == "major_wire"
    assert out.corroboration.corroborating_count == 2
    assert out.corroboration.corroboration_boost == pytest.approx(0.20)
    # 0.92 * 0.9 + 0.20 = 1.028 -> clamped 1.0
    assert out.score == pytest.approx(1.0)
    assert out.band == "proceed"
    assert out.trace_detail()          # non-empty sentence for the trace node
    assert "credibility_breakdown" in out.trace_values()


def test_verify_end_to_end_dismisses_with_a_traceable_reason(policy):
    junk = ev(
        event_id="e-junk",
        source="Some Blog",
        url="https://randomblog.example/post",
        author=None,
        title="Rumour: Acme Hldgs might be in trouble",
        entity_name="Acme Hldgs",
    )
    out = verify(junk, match_score=64, policy=policy, candidates=[])

    assert out.credibility.low_credibility is True
    assert out.corroboration.corroborating_count == 0
    assert out.band == "dismiss"
    # the counterfactual (Dev 3) reads exactly these keys:
    b = out.confidence.breakdown
    assert b["match_score"] == 64
    assert b["credibility"] < 0.7
    assert b["corroboration_boost"] == 0.0