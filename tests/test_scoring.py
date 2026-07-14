import os
import time
import pytest
import yaml
from app.models import Base, engine
from app.repositories.unit_of_work import UnitOfWork
from app.models.entities import Entity, EntityPerson
from app.services.scoring.policy import get_policy, RiskPolicy
from app.services.scoring.rule_engine import compute_delta, apply_delta, ScoreDelta
from app.services.scoring.bands import resolve_band
from app.services.scoring.velocity import compute_velocity
from app.services.scoring.propagator import propagate

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_compute_delta_table():
    policy = get_policy()
    # Test cases: (event_type, severity, jurisdiction_factor, expected_delta)
    test_cases = [
        ("pep_flag", 1.0, 1.0, 15.0),
        ("pep_flag", 0.5, 1.0, 7.5),
        ("pep_flag", 1.0, 1.3, 19.5),
        ("fatf_country_flag", 1.0, 1.0, 10.0),
        ("fatf_country_flag", 0.8, 1.3, 10.4),
        ("transaction_anomaly", 0.5, 1.0, 10.0),
        ("transaction_anomaly", 1.0, 1.3, 26.0),
        ("adverse_media", 0.5, 1.0, 6.0),
        ("adverse_media", 1.0, 1.3, 15.6),
        ("sanctions_hit", 1.0, 1.0, 40.0),
    ]
    for event_type, severity, j_factor, expected in test_cases:
        res = compute_delta(event_type, severity, j_factor, policy)
        assert res.delta == pytest.approx(expected)

def test_band_precedence():
    policy = get_policy()
    # 1. Sanctions direct hit always resolves to CRITICAL
    band, rule = resolve_band(score=10.0, velocity_multiplier=0.0, velocity_threshold=3.0, sanctions_direct_hit=True, policy=policy)
    assert band == "CRITICAL"
    assert rule == "sanctions_direct_hit"
    
    # 2. Score thresholds
    band, rule = resolve_band(score=85.0, velocity_multiplier=0.0, velocity_threshold=3.0, sanctions_direct_hit=False, policy=policy)
    assert band == "CRITICAL"
    assert rule == "score_threshold_critical"
    
    band, rule = resolve_band(score=65.0, velocity_multiplier=0.0, velocity_threshold=3.0, sanctions_direct_hit=False, policy=policy)
    assert band == "HIGH"
    assert rule == "score_threshold_high"

    band, rule = resolve_band(score=45.0, velocity_multiplier=0.0, velocity_threshold=3.0, sanctions_direct_hit=False, policy=policy)
    assert band == "MEDIUM"
    assert rule == "score_threshold_medium"

    band, rule = resolve_band(score=20.0, velocity_multiplier=0.0, velocity_threshold=3.0, sanctions_direct_hit=False, policy=policy)
    assert band == "LOW"
    assert rule == "score_threshold_low"

    # 3. Velocity promotion (e.g. LOW -> MEDIUM, MEDIUM -> HIGH, HIGH -> CRITICAL)
    band, rule = resolve_band(score=20.0, velocity_multiplier=4.0, velocity_threshold=3.0, sanctions_direct_hit=False, policy=policy)
    assert band == "MEDIUM"
    assert rule == "velocity_promotion"

    band, rule = resolve_band(score=50.0, velocity_multiplier=4.0, velocity_threshold=3.0, sanctions_direct_hit=False, policy=policy)
    assert band == "HIGH"
    assert rule == "velocity_promotion"

    band, rule = resolve_band(score=70.0, velocity_multiplier=4.0, velocity_threshold=3.0, sanctions_direct_hit=False, policy=policy)
    assert band == "CRITICAL"
    assert rule == "velocity_promotion"

def test_velocity_calculation_and_promotion():
    with UnitOfWork() as uow:
        # Create a new entity for this test
        ent = Entity(name="Velocity Test Co", risk_score=10.0, risk_band="LOW")
        uow.entities.add(ent)
        uow.commit()
        
        # Initially, velocity multiplier should be 0
        res = compute_velocity(ent.id, 72, uow)
        assert res.count == 0
        assert res.multiplier == 0.0
        
        # Apply 3 events (direct)
        policy = get_policy()
        delta = ScoreDelta(weight=10.0, severity=1.0, jurisdiction_factor=1.0, delta=10.0)
        for _ in range(3):
            apply_delta(ent.id, delta, uow, event_category="TRANSACTION", policy=policy)
            
        res = compute_velocity(ent.id, 72, uow)
        assert res.count == 3
        assert res.multiplier >= 3.0
        
        # Band should be promoted to HIGH (base score 10 + 30 = 40 -> MEDIUM, velocity promotion promotes it to HIGH)
        entity_updated = uow.entities.get(ent.id)
        assert entity_updated.risk_score == 40.0
        assert entity_updated.risk_band == "HIGH"
        
        uow.rollback()

def test_one_hop_propagation():
    with UnitOfWork() as uow:
        # Create Entity A and Entity B sharing a director "John Doe"
        ent_a = Entity(name="Entity A", risk_score=10.0, risk_band="LOW")
        ent_b = Entity(name="Entity B", risk_score=10.0, risk_band="LOW")
        uow.entities.add(ent_a)
        uow.entities.add(ent_b)
        uow.commit()
        
        p_a = EntityPerson(entity_id=ent_a.id, person_name="John Doe", role="DIRECTOR")
        p_b = EntityPerson(entity_id=ent_b.id, person_name="John Doe", role="DIRECTOR")
        uow.session.add(p_a)
        uow.session.add(p_b)
        uow.commit()
        
        # Apply delta to Entity A
        policy = get_policy()
        delta = ScoreDelta(weight=20.0, severity=1.0, jurisdiction_factor=1.0, delta=20.0)
        
        # Apply delta to A. This should propagate to B:
        # B's delta should be 20.0 * 0.35 = 7.0
        apply_delta(ent_a.id, delta, uow, event_category="TRANSACTION", policy=policy)
        
        ent_a_updated = uow.entities.get(ent_a.id)
        ent_b_updated = uow.entities.get(ent_b.id)
        
        assert ent_a_updated.risk_score == 30.0
        assert ent_b_updated.risk_score == 17.0
        
        # Verify that B has a propagated risk event which is indirect=True
        b_risk_events = uow.risk_events.list(entity_id=ent_b.id)
        assert len(b_risk_events) == 1
        assert b_risk_events[0].indirect is True
        assert b_risk_events[0].delta == 7.0
        
        uow.rollback()

def test_policy_hot_reload():
    policy_file = "policy.yaml"
    with open(policy_file, "r") as f:
        original_content = f.read()
        
    try:
        policy = get_policy()
        original_pep_weight = policy.weights["pep_flag"]
        
        # Modify pep_flag weight
        new_pep_weight = original_pep_weight + 5
        data = yaml.safe_load(original_content)
        data["weights"]["pep_flag"] = new_pep_weight
        
        # Write modified content and touch the file to trigger reload
        with open(policy_file, "w") as f:
            yaml.safe_dump(data, f)
            
        reloaded_policy = get_policy()
        assert reloaded_policy.weights["pep_flag"] == new_pep_weight
        
    finally:
        # Restore original content
        with open(policy_file, "w") as f:
            f.write(original_content)
            
        restored_policy = get_policy()
        assert restored_policy.weights["pep_flag"] == original_pep_weight
