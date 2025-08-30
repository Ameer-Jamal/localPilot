"""Runtime configuration for the local assistant."""
import os

# Model/runtime
# Comma-separated list of available models. Default falls back to ``qwen2.5-coder:14b``.
MODEL_LIST = [
    m.strip()
    for m in os.environ.get("MODEL_LIST", "qwen2.5-coder:14b").split(",")
    if m.strip()
]
# Default model, overridable via ``MODEL`` env var or first entry in ``MODEL_LIST``.
MODEL = os.environ.get("MODEL", MODEL_LIST[0])
TEMP = 0.2

# Ollama HTTP endpoints
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

# Context window for chat requests (increase if you pin long code)
NUM_CTX = 16384  # adjust build/model supports it
KEEP_ALIVE = "10m"  # keep loaded between requests
