import json
from pydantic import BaseModel
from app.repositories.unit_of_work import UnitOfWork
from app.models.sar import SARDraft
from app.services.audit_service import AuditService
from knowledge.retriever import retrieve_regulatory
from app.infrastructure.llm_gateway import LLMGateway

# The schema the LLM must conform to
class CitationOut(BaseModel):
    source: str
    passage: str

class SARNarrativeOut(BaseModel):
    narrative: str
    regulatory_basis: list[CitationOut]

class SARService:
    def __init__(self, gateway: LLMGateway = None):
        self.gateway = gateway or LLMGateway()

    async def generate(self, alert_id: str, uow: UnitOfWork) -> SARDraft:
        alert = uow.alerts.get(alert_id) # Assumes this exists
        
        # 1. Retrieve Context (RAG)
        # In reality, we'd build a better query from the alert's evidence
        passages = retrieve_regulatory("record keeping obligations for suspicious activity", k=3)
        context_str = "\n".join([f"Source: {p['metadata']['source']} - {p['text']}" for p in passages])
        
        # 2. Prompt LLM
        prompt = f"""
        Generate a Suspicious Activity Report (SAR) narrative.
        Alert details: {alert.id}
        Relevant Law:
        {context_str}
        """
        
        result = await self.gateway.complete(
            prompt=prompt,
            schema=SARNarrativeOut,
            task_tag="sar_narrative"
        )
        
        # 3. Handle Degraded mode
        if result.degraded:
            narrative = "DEGRADED MODE DRAFT: Please review manually."
            valid_citations = []
        else:
            # 4. Citation Integrity Check
            narrative = result.data.narrative
            valid_citations = []
            retrieved_texts = [p['text'] for p in passages]
            
            for citation in result.data.regulatory_basis:
                # Exact substring match to prove no hallucination
                if any(citation.passage in r_text for r_text in retrieved_texts):
                    valid_citations.append(citation.model_dump())
                else:
                    print(f"Warning: Stripped hallucinated citation: {citation.passage}")

        # 5. Persist the Draft
        draft = SARDraft(
            alert_id=alert_id,
            entity_id=alert.entity_id if hasattr(alert, 'entity_id') else 'unknown',
            version=1,
            narrative=narrative,
            citations=json.dumps(valid_citations),
            status="PENDING_REVIEW"
        )
        uow.sars.add(draft)
        
        # 6. Audit Logging
        AuditService.append(
            actor="SYSTEM_REPORTER",
            action="SAR_GENERATED",
            detail={"alert_id": alert_id, "degraded": result.degraded},
            uow=uow
        )
        
        # In a real app we'd publish `sar.ready` to the broker here
        return draft
        
    def save_edit(self, sar_id: str, narrative: str, officer: str, uow: UnitOfWork) -> SARDraft:
        old_draft = uow.sars.get(sar_id) # Assumes this exists
        
        new_draft = SARDraft(
            alert_id=old_draft.alert_id,
            entity_id=old_draft.entity_id,
            version=old_draft.version + 1,
            narrative=narrative,
            citations=old_draft.citations,
            status="PENDING_REVIEW",
            previous_version_id=old_draft.id,
            created_by=officer
        )
        uow.sars.add(new_draft)
        
        AuditService.append(
            actor=officer,
            action="SAR_EDITED",
            detail={"sar_id": new_draft.id, "previous_version": old_draft.id},
            uow=uow
        )
        return new_draft