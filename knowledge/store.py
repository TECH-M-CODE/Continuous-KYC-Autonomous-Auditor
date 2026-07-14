import chromadb
import os

# Ensure the database is saved in the /data folder
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'chroma')
os.makedirs(DB_PATH, exist_ok=True)

# Persistent client survives restarts
client = chromadb.PersistentClient(path=DB_PATH)

def get_collection(name: str):
    return client.get_or_create_collection(name=name)

# Create or get the 3 collections on startup
entity_cards = get_collection("entity_cards")
event_context = get_collection("event_context")
regulatory_corpus = get_collection("regulatory_corpus")