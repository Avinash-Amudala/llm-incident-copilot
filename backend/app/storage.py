import os
from pathlib import Path
from .config import STORAGE_DIR


def ensure_storage():
    Path(STORAGE_DIR).mkdir(parents=True, exist_ok=True)


def save_upload(filename: str, content: bytes) -> str:
    ensure_storage()
    safe = filename.replace("/", "_").replace("\\", "_")
    path = os.path.join(STORAGE_DIR, safe)
    with open(path, "wb") as f:
        f.write(content)
    return path

