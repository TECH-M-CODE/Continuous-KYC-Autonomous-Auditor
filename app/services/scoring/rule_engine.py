from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.risk import RiskEvent
from app.services.scoring.policy import RiskPolicy, get_policy

class ScoreDelta(BaseModel):
    weight: float
    severity: float
    jurisdiction_factor: float
    delta: float

def compute_delta(event_type: str, severity: float, jurisdiction_factor: float, policy: RiskPolicy) -> ScoreDelta:
    if event_type not in policy.weights:
        raise ValueError(f"Unknown event type: {event_type}")
    weight = policy.weights[event_type]
    delta = weight * severity * jurisdiction_factor
    return ScoreDelta(
        weight=weight,
        severity=severity,
        jurisdiction_factor=jurisdiction_factor,
        delta=delta
    )

def apply_delta(
    entity_id: str,
    score_delta: ScoreDelta,
    uow,
    event_id: Optional[str] = None,
    event_category: Optional[str] = None,
    reasoning: Optional[str] = None,
    indirect: bool = False,
    policy: Optional[RiskPolicy] = None
) -> float:
    entity = uow.entities.get(entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    
    if policy is None:
        policy = get_policy()
        
    old_score = entity.risk_score
    new_score = max(0.0, min(100.0, old_score + score_delta.delta))
    entity.risk_score = new_score
    
    # Save the RiskEvent row
    risk_event = RiskEvent(
        entity_id=entity_id,
        event_id=event_id,
        delta=score_delta.delta,
        weight=score_delta.weight,
        severity=str(score_delta.severity),
        jurisdiction_factor=score_delta.jurisdiction_factor,
        score_after=new_score,
        event_category=event_category,
        reasoning=reasoning,
        indirect=indirect,
        created_at=datetime.utcnow()
    )
    uow.risk_events.add(risk_event)
    uow.session.flush()
    
    # Compute velocity and resolve band
    from app.services.scoring.velocity import compute_velocity
    from app.services.scoring.bands import resolve_band
    
    velocity_res = compute_velocity(entity_id, policy.velocity.window_hours, uow)
    
    # Identify if a direct sanctions hit occurs
    sanctions_direct_hit = (
        (event_category == "SANCTION") or 
        (event_id is not None and "sanction" in str(event_category).lower()) or
        (score_delta.weight >= policy.weights.get("sanctions_hit", 40.0) and score_delta.severity >= 1.0)
    )
    
    resolved_band, rule_fired = resolve_band(
        score=new_score,
        velocity_multiplier=velocity_res.multiplier,
        velocity_threshold=policy.velocity.multiplier_threshold,
        sanctions_direct_hit=sanctions_direct_hit,
        policy=policy
    )
    entity.risk_band = resolved_band
    
    # Trigger 1-hop propagation if this is a direct event
    if not indirect and score_delta.delta != 0.0:
        from app.services.scoring.propagator import propagate
        propagate(entity_id, score_delta.delta, uow, policy)
        
    return new_score
