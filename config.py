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


def _fetch_models() -> list[str]:
    """Return a list of available models.

    Preference order:
    1. ``MODEL_LIST`` environment variable (comma separated)
    2. Query the local Ollama instance for installed models
    3. Fallback to the default ``qwen2.5-coder:14b``
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

    return ["qwen2.5-coder:14b"]


MODEL_LIST = _fetch_models()

# Default model, overridable via ``MODEL`` env var or first entry in ``MODEL_LIST``.
MODEL = os.environ.get("MODEL", MODEL_LIST[0])
TEMP = 0.2


# Context window for chat requests (increase if you pin long code)
NUM_CTX = 16384  # adjust build/model supports it
KEEP_ALIVE = "10m"  # keep loaded between requests
