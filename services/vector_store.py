import os
import chromadb
from pathlib import Path
from services.storage import DATA_DIR
import dashscope
from http import HTTPStatus

# Ensure the DB is saved persistently in the data directory
CHROMA_PATH = DATA_DIR / "chroma"
CHROMA_PATH.mkdir(parents=True, exist_ok=True)

# Initialize ChromaDB Local Client
chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))

# Create or get collections for our 3 main asset types
actors_collection = chroma_client.get_or_create_collection(name="actors")
clothes_collection = chroma_client.get_or_create_collection(name="clothes")
scenes_collection = chroma_client.get_or_create_collection(name="scenes")

def _get_collection(category: str):
    return {
        "actors": actors_collection,
        "clothes": clothes_collection,
        "scenes": scenes_collection
    }.get(category)

def get_text_embedding(text: str) -> list[float]:
    """
    Calls Dashscope text-embedding-v2 to convert text into a vector.
    """
    if not text.strip():
        return [0.0] * 1536
        
    dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
    
    try:
        resp = dashscope.TextEmbedding.call(
            model=dashscope.TextEmbedding.Models.text_embedding_v2,
            input=text
        )
        if resp.status_code == HTTPStatus.OK:
            return resp.output['embeddings'][0]['embedding']
        else:
            print(f"[-] Embedding API Error: {resp.message}")
            return [0.0] * 1536
    except Exception as e:
        print(f"[-] Embedding Exception: {e}")
        return [0.0] * 1536

def is_duplicate(category: str, description: str, embedding: list[float], threshold: float = 0.88) -> bool:
    """
    Check if a semantically similar asset already exists in the collection.
    ChromaDB's default distance metric is L2; we compare using cosine-like logic.
    Returns True if a near-duplicate is found above the threshold.
    Threshold 0.88 = 88% similarity — tune lower to be less strict, higher for more duplicates allowed.
    """
    collection = _get_collection(category)
    if not collection:
        return False

    # If collection is empty there's nothing to compare against
    try:
        count = collection.count()
        if count == 0:
            return False
    except Exception:
        return False

    try:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=1,
            include=["distances", "documents"]
        )
        distances = results.get("distances", [[]])[0]
        documents = results.get("documents", [[]])[0]
        if distances:
            # ChromaDB L2 distance: 0 = identical. Convert to 0-1 similarity.
            dist = distances[0]
            # L2 distance in normalized embedding space: similarity ≈ 1 - dist/2
            similarity = max(0.0, 1.0 - dist / 2.0)
            if similarity >= threshold:
                existing_desc = documents[0] if documents else "?"
                print(f"[~] Duplicate detected ({similarity:.0%} similar): skipping. Existing: '{existing_desc[:60]}'")
                return True
    except Exception as e:
        print(f"[-] Dedup check error: {e}")

    return False

def add_asset_to_vector_store(category: str, asset_id: str, description: str, url_path: str) -> bool:
    """
    Embeds the description and stores the asset in ChromaDB — ONLY if it's not already similar to an existing asset.
    Returns True if added, False if skipped as duplicate.
    """
    collection = _get_collection(category)
    
    if not collection or not description:
        return False
    
    embedding = get_text_embedding(description)

    # Deduplication check
    if is_duplicate(category, description, embedding):
        return False
        
    print(f"[+] Indexing {category} asset into ChromaDB: {description[:60]}")
    try:
        collection.add(
            embeddings=[embedding],
            documents=[description],
            metadatas=[{"url": url_path}],
            ids=[asset_id]
        )
        return True
    except Exception as e:
        # ID already exists — silently skip
        if "already exists" in str(e).lower():
            print(f"[~] Asset ID already in DB, skipping: {asset_id}")
        else:
            print(f"[-] ChromaDB add error: {e}")
        return False

def search_assets(category: str, query: str, top_k: int = 10) -> list[dict]:
    """
    Embeds the user query and performs a similarity search in the specified category.
    Returns a list of matched asset dicts containing id, url, and description.
    """
    collection = {
        "actors": actors_collection,
        "clothes": clothes_collection,
        "scenes": scenes_collection
    }.get(category)
    
    if not collection:
        return []
        
    query_embedding = get_text_embedding(query)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )
    
    matched_assets = []
    
    if results and results['ids'] and len(results['ids']) > 0:
        ids = results['ids'][0]
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        
        for i in range(len(ids)):
            matched_assets.append({
                "id": ids[i],
                "description": documents[i],
                "url": metadatas[i]["url"]
            })
            
    return matched_assets
