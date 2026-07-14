from knowledge.store import get_collection

def retrieve_entity_candidates(event_text: str, k: int = 3) -> list[dict]:
    """
    Retrieve top-k entity candidates from entity_cards collection.
    Matches the shape required by Sequence Diagram 6.1
    """
    collection = get_collection("entity_cards")
    
    results = collection.query(
        query_texts=[event_text],
        n_results=k
    )
    
    candidates = []
    if results and results.get("ids") and len(results["ids"]) > 0:
        for idx in range(len(results["ids"][0])):
            candidates.append({
                "entity_id": results["ids"][0][idx],
                "card_text": results["documents"][0][idx],
                "similarity": results["distances"][0][idx] if "distances" in results else None
            })
            
    return candidates

def retrieve_regulatory(query: str, k: int = 4) -> list[dict]:
    """
    Mock retriever returning canned GDPR passages for now.
    """
    return [
        {
            "text": "The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay...",
            "metadata": {"source": "GDPR", "article": "17"}
        },
        {
            "text": "Taking into account the state of the art, the costs of implementation and the nature, scope, context and purposes of processing as well as the risk...",
            "metadata": {"source": "GDPR", "article": "32"}
        }
    ][:k]