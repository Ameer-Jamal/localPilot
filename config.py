"""Runtime configuration for the local assistant."""
# Model/runtime
MODEL = "qwen2.5-coder:14b"
TEMP = 0.2

# Ollama HTTP endpoints
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

# Context window for chat requests (increase if you pin long code)
NUM_CTX = 8192  # adjust to 16384 if your build/model supports it
KEEP_ALIVE = "10m"  # keep loaded between requests
