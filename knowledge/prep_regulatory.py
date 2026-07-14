import os
from knowledge.store import get_collection
from knowledge.chunker import chunk_regulatory

# Dummy text for Sprint 1 until the real dataset is provided
dummy_gdpr_text = """
Article 17
Right to erasure ('right to be forgotten')
1. The data subject shall have the right to obtain from the controller the erasure of personal data concerning him or her without undue delay and the controller shall have the obligation to erase personal data without undue delay where one of the following grounds applies:
(a) the personal data are no longer necessary in relation to the purposes for which they were collected or otherwise processed;
(b) the data subject withdraws consent on which the processing is based according to point (a) of Article 6(1), or point (a) of Article 9(2), and where there is no other legal ground for the processing;
(c) the data subject objects to the processing pursuant to Article 21(1) and there are no overriding legitimate grounds for the processing, or the data subject objects to the processing pursuant to Article 21(2);
(d) the personal data have been unlawfully processed;
(e) the personal data have to be erased for compliance with a legal obligation in Union or Member State law to which the controller is subject;
(f) the personal data have been collected in relation to the offer of information society services referred to in Article 8(1).

Article 32
Security of processing
1. Taking into account the state of the art, the costs of implementation and the nature, scope, context and purposes of processing as well as the risk of varying likelihood and severity for the rights and freedoms of natural persons, the controller and the processor shall implement appropriate technical and organisational measures to ensure a level of security appropriate to the risk.
"""

def prep_regulatory():
    print("Prepping regulatory documents...")
    
    # Run the chunker
    chunks = chunk_regulatory(
        text=dummy_gdpr_text,
        source="GDPR",
        article="17_and_32",
        max_words=50,
        overlap=10
    )
    
    print(f"Generated {len(chunks)} chunks.")
    
    if chunks:
        print("\nSample chunk:")
        print(f"Text: {chunks[0]['text']}...")
        print(f"Metadata: {chunks[0]['metadata']}")
        
    print("\nNote: Actual full indexing can finish in Sprint 2/3. Parsing of dataset formats is done.")

if __name__ == "__main__":
    prep_regulatory()