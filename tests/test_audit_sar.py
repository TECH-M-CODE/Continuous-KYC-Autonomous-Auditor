import pytest
import json
from app.models import Base, engine
from app.models.entities import Entity
from app.models.events import Alert
from app.models.audit import AuditLog
from app.repositories.unit_of_work import UnitOfWork
from app.services.audit_service import AuditService
from app.services.sar_services import SARService, SARNarrativeOut, CitationOut
from app.infrastructure.llm_gateway import GatewayResult

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_audit_chain_integrity():
    # 1. Append 50 entries
    with UnitOfWork() as uow:
        for i in range(50):
            actor = "AI_AGENT" if i % 2 == 0 else "HUMAN_OFFICER"
            AuditService.append(
                actor=actor,
                action="TEST_ACTION",
                detail={"step": i},
                uow=uow
            )
        uow.commit()

    # 2. Verify the chain is valid
    with UnitOfWork() as uow:
        result = AuditService.verify_chain(uow)
        assert result["valid"] is True
        assert result["checked"] == 50

    # 3. Tamper with row 20's detail
    with UnitOfWork() as uow:
        tampered_log = uow.session.query(AuditLog).filter(AuditLog.seq == 20).first()
        tampered_log.payload = '{"step":999}' # Tampering without updating hash
        uow.commit()

    # 4. Verify chain catches it
    with UnitOfWork() as uow:
        result = AuditService.verify_chain(uow)
        assert result["valid"] is False
        assert result["first_bad_seq"] == 20

class MockGatewayForSAR:
    async def complete(self, prompt, schema, task_tag, use_cache=True):
        # Return a mix of valid and hallucinated citations
        fake_data = SARNarrativeOut(
            narrative="This is a test SAR.",
            regulatory_basis=[
                # Valid because this text is actually in the GDPR chunk we seeded
                CitationOut(source="GDPR", passage="Right to erasure"),
                # Hallucinated! This text doesn't exist in the chunk
                CitationOut(source="GDPR", passage="The user must pay 500 dollars")
            ]
        )
        return GatewayResult(
            ok=True,
            data=fake_data,
            degraded=False,
            attempts=1,
            model_used="mock",
            from_cache=False,
            task_tag=task_tag
        )

@pytest.mark.asyncio
async def test_sar_citation_integrity():
    # Setup Entity and Alert for the SAR service
    with UnitOfWork() as uow:
        entity = Entity(id="SAR_ENT_1", name="Test Entity", jurisdiction="US", sector="Tech", risk_score=10, risk_band="LOW", status="ACTIVE", watched=True)
        uow.entities.add(entity)
        uow.session.flush()
        
        alert = Alert(id="SAR_ALERT_1", entity_id="SAR_ENT_1", trigger_event_id="dummy", priority="HIGH", status="OPEN", band="high")
        uow.alerts.add(alert)
        uow.commit()

    # Run SAR generation with our mock gateway
    mock_gateway = MockGatewayForSAR()
    sar_service = SARService(gateway=mock_gateway)
    
    with UnitOfWork() as uow:
        draft = await sar_service.generate("SAR_ALERT_1", uow)
        uow.commit()
        
        # Verify the draft stripped the hallucinated citation
        citations = json.loads(draft.citations)
        assert len(citations) == 1
        assert citations[0]["passage"] == "Right to erasure"
