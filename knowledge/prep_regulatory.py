import os
from knowledge.store import get_collection
from knowledge.chunker import chunk_regulatory

dummy_gdpr_text = """
Article 17
Right to erasure ('right to be forgotten')
1. The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies:
(a) the personal data are no longer necessary in relation to the purposes for which they were collected or otherwise processed;

Article 30
Records of processing activities
1. Each controller and, where applicable, the controller's representative, shall maintain a record of processing activities under its responsibility. That record shall contain all of the following information...
"""

def prep_regulatory():
    print("Prepping regulatory documents and indexing into ChromaDB...")
    collection = get_collection("regulatory_corpus")
    
    chunks = chunk_regulatory(
        text=dummy_gdpr_text,
        source="GDPR",
        article="17_and_30",
        max_words=50,
        overlap=10
    )
    
    ids = []
    documents = []
    metadatas = []
    
    for i, chunk in enumerate(chunks):
        ids.append(f"gdpr_chunk_{i}")
        documents.append(chunk["text"])
        metadatas.append(chunk["metadata"])
        
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    print(f"Indexed {len(chunks)} chunks into regulatory_corpus.")

if __name__ == "__main__":
    prep_regulatory()