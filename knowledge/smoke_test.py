import sys
from knowledge.index_entities import index_entities
from knowledge.retriever import retrieve_entity_candidates

def run_smoke_test():
    print("--- Running Smoke Test ---")
    
    # 1. Index the 10 fake entities
    print("\n1. Indexing entities...")
    index_entities()
    
    # 2. Query for "Acme Holdings"
    query = "fraud investigation into Acme Holdings"
    print(f"\n2. Querying for: '{query}'")
    candidates = retrieve_entity_candidates(query, k=3)
    
    # 3. Verify top-3 results include Acme
    print("\n3. Results:")
    acme_found = False
    for i, candidate in enumerate(candidates):
        print(f"  Rank {i+1}: Similarity {candidate['similarity']:.4f}")
        print(f"  Card Text:\n{candidate['card_text']}")
        print("-" * 20)
        
        if "Acme Holdings" in candidate['card_text']:
            acme_found = True
            
    if acme_found:
        print("\nSUCCESS: 'Acme Holdings' was found in the top-3 results.")
        return 0
    else:
        print("\nFAILURE: 'Acme Holdings' was NOT found in the top-3 results.")
        return 1

if __name__ == "__main__":
    sys.exit(run_smoke_test())
