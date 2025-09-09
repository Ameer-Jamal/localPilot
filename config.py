"""Runtime configuration for the local assistant."""
import os

import requests

# ---------------------------------------------------------------------------
# Ollama HTTP endpoints

OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api")
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/chat"
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/tags"


# ---------------------------------------------------------------------------
# Model/runtime


def fetch_ollama_models() -> list[str]:
    """Return a list of available models.

    Preference order:
    1. ``MODEL_LIST`` environment variable (comma separated)
    2. Query the local Ollama instance for models
    """

    env = os.environ.get("MODEL_LIST")
    if env:
        models = [m.strip() for m in env.split(",") if m.strip()]
        if models:
            return models

    try:
        r = requests.get(OLLAMA_TAGS_URL, timeout=1)
        r.raise_for_status()
        data = r.json()
        models = []
        for m in data.get("models", []):
            name = m.get("name") or m.get("model")
            if name:
                models.append(name)
        if models:
            return models
    except Exception:
        pass

    return []


def is_ollama_running() -> bool:
    """Return True if the Ollama server responds, False otherwise."""
    try:
        r = requests.get(OLLAMA_TAGS_URL, timeout=1)
        r.raise_for_status()
        return True
    except Exception:
        return False


MODEL_LIST = fetch_ollama_models()

MODEL = MODEL_LIST[0] if MODEL_LIST else []
TEMP = 0.2

# Context window for chat requests (increase if you pin long code)
NUM_CTX = 16384  # adjust build/model supports it
KEEP_ALIVE = "10m"  # keep loaded between requests
