import uuid
from knowledge.store import get_collection
from knowledge.chunker import chunk_entity_card

# Create 10 fake entities including Acme Holdings
fake_entities = [
    {
        "id": str(uuid.uuid4()),
        "name": "Acme Holdings",
        "country": "Cayman Islands",
        "sector": "Real Estate",
        "sector_risk": "High",
        "pep_flag": False,
        "sanctions_flag": False,
        "fatf_country_flag": True,
        "base_score": 60,
        "current_score": 60,
        "watched": True
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Global Tech Corp",
        "country": "USA",
        "sector": "Technology",
        "sector_risk": "Low",
        "pep_flag": False,
        "sanctions_flag": False,
        "fatf_country_flag": False,
        "base_score": 10,
        "current_score": 10,
        "watched": False
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Oceanic Airlines",
        "country": "Australia",
        "sector": "Transportation",
        "sector_risk": "Medium",
        "pep_flag": False,
        "sanctions_flag": False,
        "fatf_country_flag": False,
        "base_score": 25,
        "current_score": 25,
        "watched": False
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Sterling Cooper",
        "country": "UK",
        "sector": "Advertising",
        "sector_risk": "Low",
        "pep_flag": False,
        "sanctions_flag": False,
        "fatf_country_flag": False,
        "base_score": 10,
        "current_score": 10,
        "watched": False
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Wayne Enterprises",
        "country": "USA",
        "sector": "Defense",
        "sector_risk": "High",
        "pep_flag": True,
        "sanctions_flag": False,
        "fatf_country_flag": False,
        "base_score": 75,
        "current_score": 75,
        "watched": True
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Umbrella Corp",
        "country": "Switzerland",
        "sector": "Pharmaceuticals",
        "sector_risk": "High",
        "pep_flag": False,
        "sanctions_flag": True,
        "fatf_country_flag": False,
        "base_score": 90,
        "current_score": 90,
        "watched": True
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Massive Dynamic",
        "country": "USA",
        "sector": "Technology",
        "sector_risk": "Low",
        "pep_flag": False,
        "sanctions_flag": False,
        "fatf_country_flag": False,
        "base_score": 10,
        "current_score": 10,
        "watched": False
    },
    {
        "id": str(uuid.uuid4()),
        "name": "LexCorp",
        "country": "USA",
        "sector": "Technology",
        "sector_risk": "Medium",
        "pep_flag": True,
        "sanctions_flag": False,
        "fatf_country_flag": False,
        "base_score": 60,
        "current_score": 60,
        "watched": True
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Cyberdyne Systems",
        "country": "USA",
        "sector": "Defense",
        "sector_risk": "High",
        "pep_flag": False,
        "sanctions_flag": False,
        "fatf_country_flag": False,
        "base_score": 50,
        "current_score": 50,
        "watched": False
    },
    {
        "id": str(uuid.uuid4()),
        "name": "InGen",
        "country": "Costa Rica",
        "sector": "Biotech",
        "sector_risk": "High",
        "pep_flag": False,
        "sanctions_flag": False,
        "fatf_country_flag": False,
        "base_score": 40,
        "current_score": 40,
        "watched": False
    }
]

def index_entities():
    print(f"Indexing {len(fake_entities)} fake entities into ChromaDB...")
    collection = get_collection("entity_cards")
    
    ids = []
    documents = []
    metadatas = []
    
    for entity in fake_entities:
        card_text = chunk_entity_card(entity)
        ids.append(entity["id"])
        documents.append(card_text)
        metadatas.append({"name": entity["name"], "watched": entity["watched"]})
        
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    print("Indexing complete.")

if __name__ == "__main__":
    index_entities()