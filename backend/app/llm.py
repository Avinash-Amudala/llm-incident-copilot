import requests
from typing import List
from .config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_EMBED_MODEL


def ollama_embed(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using Ollama's embedding model."""
    vectors: List[List[float]] = []
    for t in texts:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": t},
            timeout=60,
        )
        r.raise_for_status()
        vectors.append(r.json()["embedding"])
    return vectors


def ollama_chat(system: str, user: str) -> str:
    """Send a chat request to Ollama and return the response."""
    r = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]

