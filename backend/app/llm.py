import requests
import logging
import concurrent.futures
import urllib3
from typing import List
from .config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_EMBED_MODEL,
    GROQ_API_KEY, GROQ_MODEL, INFERENCE_PROVIDER, EMBEDDING_CONCURRENCY
)

logger = logging.getLogger(__name__)

# Disable SSL warnings for corporate networks with proxy/MITM certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# connection pool for better performance
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=3)
session.mount('http://', adapter)
session.mount('https://', adapter)

# Disable SSL verification for corporate networks (Groq API behind proxy)
session.verify = False

# thread pool for concurrent embedding
executor = concurrent.futures.ThreadPoolExecutor(max_workers=EMBEDDING_CONCURRENCY)


def get_inference_provider() -> str:
    """Determine which inference provider to use."""
    if INFERENCE_PROVIDER == "groq" or (INFERENCE_PROVIDER == "auto" and GROQ_API_KEY):
        return "groq"
    return "ollama"


def check_ollama_connection() -> bool:
    """Verify Ollama is reachable and has required models."""
    try:
        r = session.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            has_embed = any(OLLAMA_EMBED_MODEL in m for m in models)
            has_llm = any(OLLAMA_MODEL in m for m in models)
            if not has_embed:
                logger.warning(f"Embedding model '{OLLAMA_EMBED_MODEL}' not found. Available: {models}")
            if not has_llm and get_inference_provider() == "ollama":
                logger.warning(f"LLM model '{OLLAMA_MODEL}' not found. Available: {models}")
            return True
        return False
    except Exception as e:
        logger.error(f"Cannot connect to Ollama at {OLLAMA_BASE_URL}: {e}")
        return False


def _embed_single(text: str) -> List[float]:
    """Embed a single text. Used for concurrent execution."""
    try:
        truncated = text[:4000] if len(text) > 4000 else text
        r = session.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": truncated},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["embedding"]
    except requests.exceptions.Timeout:
        logger.warning("Timeout embedding text, using zero vector")
        return [0.0] * 768
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return [0.0] * 768


def ollama_embed(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings using Ollama's embedding model.
    Uses concurrent execution for much faster processing.
    """
    if not texts:
        return []

    total = len(texts)
    logger.info(f"Embedding {total} texts using {EMBEDDING_CONCURRENCY} concurrent workers...")

    # use thread pool for concurrent embedding - preserves order
    vectors = list(executor.map(_embed_single, texts))

    logger.info(f"Completed embedding {len(vectors)} texts")
    return vectors


def _groq_chat(system: str, user: str, timeout: int = 60) -> str:
    """Send chat request to Groq API (ultra-fast cloud inference)."""
    try:
        logger.info(f"Sending chat request to Groq ({GROQ_MODEL})...")
        r = session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        response = r.json()["choices"][0]["message"]["content"]
        logger.info(f"Got Groq response ({len(response)} chars)")
        return response
    except requests.exceptions.Timeout:
        logger.error(f"Groq request timed out after {timeout}s")
        return "Analysis timed out. Please try again."
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return f"Error with Groq API: {str(e)}"


def _ollama_chat(system: str, user: str, timeout: int = 180) -> str:
    """Send chat request to local Ollama."""
    try:
        logger.info(f"Sending chat request to Ollama ({OLLAMA_MODEL})...")
        r = session.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {
                    "num_ctx": 4096,
                    "temperature": 0.3,
                }
            },
            timeout=timeout,
        )
        r.raise_for_status()
        response = r.json()["message"]["content"]
        logger.info(f"Got Ollama response ({len(response)} chars)")
        return response
    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timed out after {timeout}s")
        return "Analysis timed out. The model may still be loading. Please try again."
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return f"Error with Ollama: {str(e)}. Make sure Ollama is running."


def ollama_chat(system: str, user: str, timeout: int = 180) -> str:
    """
    Send a chat request to the configured LLM provider.
    Uses Groq (fast cloud) if API key is set, otherwise falls back to Ollama (local).
    """
    provider = get_inference_provider()

    if provider == "groq":
        return _groq_chat(system, user, min(timeout, 60))
    else:
        return _ollama_chat(system, user, timeout)


def get_available_models() -> List[str]:
    """Get list of available models."""
    models = []

    # always check Ollama for embedding models
    try:
        r = session.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
    except:
        pass

    # add note about Groq if available
    if GROQ_API_KEY:
        models.append(f"groq:{GROQ_MODEL}")

    return models

