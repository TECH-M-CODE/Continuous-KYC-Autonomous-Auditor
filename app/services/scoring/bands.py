from app.services.scoring.policy import RiskPolicy

def resolve_band(
    score: float,
    velocity_multiplier: float,
    velocity_threshold: float,
    sanctions_direct_hit: bool,
    policy: RiskPolicy
) -> tuple[str, str]:
    """
    Resolve the risk band with order of precedence:
    1. Direct sanctions hit -> CRITICAL (regardless of score)
    2. Score thresholds (40/60/80)
    3. Velocity promotion (multiplier >= threshold -> promote band by 1 level)
    
    Returns a tuple of (resolved_band, rule_fired).
    """
    if sanctions_direct_hit:
        return "CRITICAL", "sanctions_direct_hit"
        
    medium_threshold = policy.bands.get("medium", 40.0)
    high_threshold = policy.bands.get("high", 60.0)
    critical_threshold = policy.bands.get("critical", 80.0)
    
    if score >= critical_threshold:
        base_band = "CRITICAL"
        rule = "score_threshold_critical"
    elif score >= high_threshold:
        base_band = "HIGH"
        rule = "score_threshold_high"
    elif score >= medium_threshold:
        base_band = "MEDIUM"
        rule = "score_threshold_medium"
    else:
        base_band = "LOW"
        rule = "score_threshold_low"
        
    # Check velocity promotion
    if velocity_multiplier >= velocity_threshold:
        promotions = {
            "LOW": "MEDIUM",
            "MEDIUM": "HIGH",
            "HIGH": "CRITICAL",
            "CRITICAL": "CRITICAL"
        }
        promoted_band = promotions[base_band]
        if promoted_band != base_band:
            return promoted_band, "velocity_promotion"
            
    return base_band, rule
