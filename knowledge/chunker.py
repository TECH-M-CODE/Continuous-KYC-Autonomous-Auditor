def chunk_entity_card(entity: dict) -> str:
    """
    Render one entity into a compact text card.
    Expects entity to be a dictionary resembling the EntityProfile schema.
    """
    name = entity.get('name', 'Unknown')
    country = entity.get('country', 'Unknown')
    sector = entity.get('sector', 'Unknown')
    
    flags = []
    if entity.get('pep_flag'): flags.append("PEP")
    if entity.get('sanctions_flag'): flags.append("Sanctioned")
    if entity.get('fatf_country_flag'): flags.append("FATF Country")
    
    flags_str = ", ".join(flags) if flags else "None"
    
    # This string format is what ChromaDB will embed and search against
    return f"Entity Name: {name}\nCountry: {country}\nSector: {sector}\nRisk Flags: {flags_str}"

def chunk_regulatory(text: str, source: str = "GDPR", article: str = "Unknown", max_words: int = 200, overlap: int = 50) -> list[dict]:
    """
    Sliding-window chunker for regulatory text.
    Returns list of dicts with text and metadata.
    """
    words = text.split()
    chunks = []
    
    start = 0
    while start < len(words):
        end = start + max_words
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)
        
        chunks.append({
            "text": chunk_text,
            "metadata": {
                "source": source,
                "article": article
            }
        })
        start += (max_words - overlap)
        
    return chunks