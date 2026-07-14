from app.models.entities import EntityPerson
from app.services.scoring.policy import RiskPolicy

def propagate(entity_id: str, delta: float, uow, policy: RiskPolicy):
    """
    Find all related entities that share directors/UBOs with the source entity
    and propagate the risk delta multiplied by the propagation factor.
    """
    # 1. Find all person names associated with the source entity
    person_names = [p.person_name for p in uow.session.query(EntityPerson).filter(
        EntityPerson.entity_id == entity_id
    ).all()]
    
    if not person_names:
        return
        
    # 2. Find all related entity_ids sharing these person names
    related_persons = uow.session.query(EntityPerson).filter(
        EntityPerson.person_name.in_(person_names),
        EntityPerson.entity_id != entity_id
    ).all()
    
    related_entity_ids = list(set(rp.entity_id for rp in related_persons))
    
    if not related_entity_ids:
        return
        
    # 3. Propagate score delta
    propagation_factor = policy.propagation_factor
    propagated_delta = delta * propagation_factor
    
    from app.services.scoring.rule_engine import apply_delta, ScoreDelta
    
    score_delta = ScoreDelta(
        weight=0.0,
        severity=1.0,
        jurisdiction_factor=1.0,
        delta=propagated_delta
    )
    
    for rel_id in related_entity_ids:
        reasoning = f"Indirect risk propagation from related entity {entity_id} via shared relationship."
        apply_delta(
            entity_id=rel_id,
            score_delta=score_delta,
            uow=uow,
            event_category="PROPAGATED",
            reasoning=reasoning,
            indirect=True  # Prevent infinite cycle
        )
