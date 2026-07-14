from datetime import datetime, timedelta
from pydantic import BaseModel
from app.models.risk import RiskEvent

class VelocityResult(BaseModel):
    count: int
    baseline: float
    multiplier: float

def compute_velocity(entity_id: str, window_hours: int, uow) -> VelocityResult:
    now = datetime.utcnow()
    window_start = now - timedelta(hours=window_hours)
    
    entity = uow.entities.get(entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    
    # 1. Count events in trailing window
    events_in_window = uow.session.query(RiskEvent).filter(
        RiskEvent.entity_id == entity_id,
        RiskEvent.created_at >= window_start
    ).count()
    
    # 2. Compute historical baseline rate (events per window_hours)
    history_start = entity.created_at or (now - timedelta(days=30))
    
    if history_start >= window_start:
        # Default baseline if entity is too new to have historical baseline
        baseline = 1.0
    else:
        history_duration_hours = (window_start - history_start).total_seconds() / 3600.0
        events_before_window = uow.session.query(RiskEvent).filter(
            RiskEvent.entity_id == entity_id,
            RiskEvent.created_at < window_start
        ).count()
        
        history_duration_hours = max(1.0, history_duration_hours)
        baseline_rate_per_hour = events_before_window / history_duration_hours
        baseline = baseline_rate_per_hour * window_hours
        
    # Clamp baseline to a minimum of 1.0 to prevent division anomalies
    baseline = max(1.0, baseline)
    multiplier = float(events_in_window) / baseline
    
    return VelocityResult(
        count=events_in_window,
        baseline=baseline,
        multiplier=multiplier
    )
