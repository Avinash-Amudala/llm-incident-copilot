import uuid
from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from .config import QDRANT_URL, COLLECTION_NAME

_client = QdrantClient(url=QDRANT_URL)


def ensure_collection(vector_size: int):
    """Ensure the Qdrant collection exists with the correct vector size."""
    collections = [c.name for c in _client.get_collections().collections]
    if COLLECTION_NAME in collections:
        return
    _client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def upsert_chunks(vectors: List[List[float]], chunks: List[str], metas: List[Dict]) -> int:
    """Upsert chunk vectors into Qdrant with metadata."""
    ensure_collection(vector_size=len(vectors[0]))
    points: List[PointStruct] = []
    for v, c, m in zip(vectors, chunks, metas):
        chunk_id = str(uuid.uuid4())
        payload = {"chunk_id": chunk_id, "text": c, **m}
        points.append(PointStruct(id=chunk_id, vector=v, payload=payload))
    _client.upsert(collection_name=COLLECTION_NAME, points=points)
    return len(points)


def search(query_vector: List[float], top_k: int = 6):
    """Search for similar chunks in Qdrant."""
    hits = _client.search(collection_name=COLLECTION_NAME, query_vector=query_vector, limit=top_k)
    return hits

