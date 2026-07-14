import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from app.models import Base, engine
from app.models.entities import Entity, EntityPerson, AccountEntityMap
from app.models.events import RawEvent, Alert
from app.models.risk import RiskEvent
from app.models.sar import SARDraft
from app.models.audit import AuditLog
from app.models.sanctions import SanctionsCache
from app.repositories.unit_of_work import UnitOfWork

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Setup clean test tables
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_sqlite_wal_mode():
    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()
        
        assert journal_mode.lower() == "wal"
        assert foreign_keys == 1

def test_events_raw_duplicate_content_hash():
    e1 = RawEvent(content_hash="hash_1", content="Content 1")
    e2 = RawEvent(content_hash="hash_1", content="Content 2")
    
    with UnitOfWork() as uow:
        # Clear existing just in case
        existing = uow.session.query(RawEvent).filter(RawEvent.content_hash == "hash_1").all()
        for ext in existing:
            uow.session.delete(ext)
        uow.commit()
        
        uow.events.add(e1)
        uow.commit()
        
    with pytest.raises(IntegrityError):
        with UnitOfWork() as uow:
            uow.events.add(e2)
            uow.commit()

def test_round_trip_crud():
    # Test a full round-trip of adding and getting items for each table using UoW.
    with UnitOfWork() as uow:
        # 1. Entity
        entity = Entity(
            id="T_ENTITY_001",
            name="Test Company LLC",
            jurisdiction="US",
            sector="Finance",
            risk_score=15.0,
            risk_band="LOW",
            status="ACTIVE",
            watched=False
        )
        uow.entities.add(entity)
        uow.session.flush()
        
        # 2. EntityPerson
        person = EntityPerson(
            entity_id="T_ENTITY_001",
            person_name="John Doe",
            role="DIRECTOR",
            ownership_percentage=25.0
        )
        uow.session.add(person)
        uow.session.flush()
        
        # 3. AccountEntityMap
        acc_map = AccountEntityMap(
            account_no="ACC123456",
            entity_id="T_ENTITY_001"
        )
        uow.session.add(acc_map)
        uow.session.flush()
        
        # 4. RawEvent
        raw_event = RawEvent(
            id="T_EVENT_001",
            content_hash="hash_crud_1",
            content="Raw adverse media snippet",
            processed=False
        )
        uow.events.add(raw_event)
        uow.session.flush()
        
        # 5. RiskEvent
        risk_event = RiskEvent(
            id="T_RISK_001",
            entity_id="T_ENTITY_001",
            event_id="T_EVENT_001",
            delta=15.0,
            weight=1.0,
            severity="MEDIUM",
            score_after=15.0
        )
        uow.risk_events.add(risk_event)
        uow.session.flush()
        
        # 6. Alert
        alert = Alert(
            id="T_ALERT_001",
            entity_id="T_ENTITY_001",
            trigger_event_id="T_RISK_001",
            priority="MEDIUM",
            status="OPEN",
            band="medium"
        )
        uow.alerts.add(alert)
        uow.session.flush()
        
        # 7. SARDraft
        sar = SARDraft(
            id="T_SAR_001",
            alert_id="T_ALERT_001",
            entity_id="T_ENTITY_001",
            version=1,
            narrative="Suspicious transactions pattern noticed."
        )
        uow.sars.add(sar)
        uow.session.flush()
        
        # 8. AuditLog
        audit = AuditLog(
            id="T_AUDIT_001",
            entity_id="T_ENTITY_001",
            actor_id="system",
            action="SCORE_UPDATED",
            entry_hash="hash_audit_1",
            prev_hash="GENESIS"
        )
        uow.audit_log.add(audit)
        uow.session.flush()
        
        # 9. SanctionsCache
        sanction = SanctionsCache(
            id="T_SANCTION_001",
            name="John Doe",
            name_normalized="johndoe",
            list_source="OFAC"
        )
        uow.sanctions.add(sanction)
        uow.session.flush()
        
        uow.commit()

    # Verify retrieval
    with UnitOfWork() as uow:
        assert uow.entities.get("T_ENTITY_001").name == "Test Company LLC"
        
        persons = uow.session.query(EntityPerson).filter_by(entity_id="T_ENTITY_001").all()
        assert len(persons) == 1
        assert persons[0].person_name == "John Doe"
        
        accs = uow.session.query(AccountEntityMap).filter_by(entity_id="T_ENTITY_001").all()
        assert len(accs) == 1
        assert accs[0].account_no == "ACC123456"
        
        assert uow.events.get("T_EVENT_001").content_hash == "hash_crud_1"
        assert uow.risk_events.get("T_RISK_001").severity == "MEDIUM"
        assert uow.alerts.get("T_ALERT_001").band == "medium"
        assert uow.sars.get("T_SAR_001").narrative == "Suspicious transactions pattern noticed."
        
        audits = uow.audit_log.list(entity_id="T_ENTITY_001")
        assert len(audits) == 1
        assert audits[0].action == "SCORE_UPDATED"
        
        assert uow.sanctions.get("T_SANCTION_001").name_normalized == "johndoe"
