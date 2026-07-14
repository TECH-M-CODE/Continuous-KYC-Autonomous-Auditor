from knowledge.store import get_collection

def retrieve_entity_candidates(event_text: str, k: int = 3) -> list[dict]:
    # (Existing code from sprint 1)
    pass

def retrieve_regulatory(query: str, k: int = 4) -> list[dict]:
    """Retrieve top-k regulatory passages using ChromaDB semantic search."""
    collection = get_collection("regulatory_corpus")
    
    results = collection.query(
        query_texts=[query],
        n_results=k
    )
    
    passages = []
    if results and results.get("ids") and len(results["ids"]) > 0:
        for idx in range(len(results["ids"][0])):
            passages.append({
                "text": results["documents"][0][idx],
                "metadata": results["metadatas"][0][idx]
            })
            
    return passages