"""Index the real seeded entities from SQLite into ChromaDB's `entity_cards`
collection so the Resolver agent can match live events to real entity IDs.

Previously this file indexed 10 hardcoded fake entities (Acme/Wayne/Umbrella),
which meant `resolver.retrieve_entity_candidates()` could never resolve an event
to a real `C_0001`-style entity. It now reads whatever `seed_entities` put in the
database. Re-run after every re-seed:  python -m knowledge.index_entities
"""

from knowledge.store import get_collection
from knowledge.chunker import chunk_entity_card
from app.repositories.unit_of_work import UnitOfWork


def _entity_to_card_dict(entity) -> dict:
    """Map the real Entity ORM row onto the dict shape chunk_entity_card expects.

    The domain model stores `jurisdiction`/`sector`/`risk_band` (no separate
    country/pep/sanctions flags), so we derive the card fields from what exists.
    """
    band = (entity.risk_band or "").upper()
    return {
        "id": entity.id,
        "name": entity.name,
        "country": entity.jurisdiction or "Unknown",
        "sector": entity.sector or "Unknown",
        # No dedicated flag columns in the model; surface risk band as a soft
        # signal so the embedded card still carries the entity's risk posture.
        "sanctions_flag": band == "CRITICAL",
        "pep_flag": False,
        "fatf_country_flag": False,
    }


def index_entities():
    with UnitOfWork() as uow:
        entities = uow.entities.list()

    if not entities:
        print(
            "No entities found in the database. Run `python -m data.seed.seed_entities` "
            "first, then re-run this indexer."
        )
        return

    print(f"Indexing {len(entities)} real entities into ChromaDB...")
    collection = get_collection("entity_cards")

    # Purge any stale cards (e.g. the old hardcoded Acme/Wayne fakes, or entities
    # dropped from a prior seed) so resolution only ever matches current DB rows.
    real_ids = {e.id for e in entities}
    existing = collection.get(include=[])
    stale = [cid for cid in existing.get("ids", []) if cid not in real_ids]
    if stale:
        collection.delete(ids=stale)
        print(f"Removed {len(stale)} stale entity cards.")

    ids, documents, metadatas = [], [], []
    for entity in entities:
        card = _entity_to_card_dict(entity)
        ids.append(entity.id)
        documents.append(chunk_entity_card(card))
        metadatas.append(
            {
                "name": entity.name,
                "watched": bool(entity.watched),
                "jurisdiction": entity.jurisdiction or "",
                "risk_band": entity.risk_band or "LOW",
            }
        )

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Indexing complete. {len(ids)} entity cards upserted.")


if __name__ == "__main__":
    index_entities()
