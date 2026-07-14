import chromadb.utils.embedding_functions as embedding_functions

# Use the default sentence-transformers model for Sprint 1
default_ef = embedding_functions.DefaultEmbeddingFunction()

def embed(texts: list[str]) -> list[list[float]]:
    """
    Thin wrapper over the embedding function. 
    Returns vectors for the given texts.
    """
    return default_ef(texts)