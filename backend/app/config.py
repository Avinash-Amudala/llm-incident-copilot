import os

# Vector database config
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "log_chunks")

# Ollama config (local inference)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# Groq config (cloud inference - much faster, free tier available)
# Get your API key at https://console.groq.com/keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")  # fast and capable

# Inference provider: "ollama" (local) or "groq" (cloud, faster)
# If GROQ_API_KEY is set, uses Groq by default for chat (embeddings still use Ollama)
INFERENCE_PROVIDER = os.getenv("INFERENCE_PROVIDER", "auto")

# Storage and CORS
STORAGE_DIR = os.getenv("STORAGE_DIR", "/tmp/llm-incident-copilot")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]

# Performance tuning
MAX_CHUNKS = int(os.getenv("MAX_CHUNKS", "50"))  # limit chunks to prevent timeouts
EMBEDDING_CONCURRENCY = int(os.getenv("EMBEDDING_CONCURRENCY", "5"))  # parallel embedding calls

