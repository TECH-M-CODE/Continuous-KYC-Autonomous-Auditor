"""SAR draft creation service.

This thin service isolates the business logic of creating and versioning SAR
drafts from the agent that calls it, keeping the reporter node clean.

All writes happen inside the UoW passed by the caller; the caller commits.
"""

from __future__ import annotations

import json
import logging

from app.models.sar import SARDraft
from app.repositories.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)


def create_sar_draft(
    entity_id: str,
    narrative: str,
    citations: list[dict],
    uow: UnitOfWork,
    *,
    alert_id: str | None = None,
    created_by: str = "system",
) -> SARDraft:
    """Persist a new SAR draft and return the ORM object.

    Parameters
    ----------
    entity_id:
        The entity the SAR covers.
    narrative:
        LLM-generated narrative text.
    citations:
        List of ``{citation, passage}`` dicts produced by the reporter prompt.
    uow:
        Open UnitOfWork — the caller commits.
    alert_id:
        Optional link back to the Alert that triggered this SAR.
    created_by:
        Actor string, default ``"system"`` for agent-generated drafts.
    """
    citations_json = json.dumps(citations, ensure_ascii=False)

    draft = SARDraft(
        alert_id=alert_id,
        entity_id=entity_id,
        version=1,
        narrative=narrative,
        citations=citations_json,
        status="DRAFT",
        created_by=created_by,
    )
    uow.sars.add(draft)
    log.debug("SAR draft queued for entity=%s alert=%s", entity_id, alert_id)
    return draft


def get_citations(sar: SARDraft) -> list[dict]:
    """Deserialize the citations JSON column back to a Python list."""
    if not sar.citations:
        return []
    try:
        return json.loads(sar.citations)
    except (json.JSONDecodeError, TypeError):
        return []


__all__ = ["create_sar_draft", "get_citations"]
