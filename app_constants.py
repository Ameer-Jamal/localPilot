from __future__ import annotations

from pathlib import Path

NEW_CHAT_TITLE = "New Chat"
SETTINGS_LABEL = "Settings"
HISTORY_LABEL = "History"
SHOW_HISTORY_LABEL = "Show History"
NO_OLLAMA_MODELS_FOUND = "No Ollama Models Found"
QUICK_PROMPTS_ITEMS_KEY = "quick_prompts/items"

JSON_CONTENT_TYPE = "application/json"
JSON_HEADERS = {"Content-Type": JSON_CONTENT_TYPE}

LOCALPILOT_TOOL_NAME = "LocalPilot"
LOCALPILOT_TOOL_DESCRIPTION = "Send current selection to LocalPilot"
EXTERNAL_TOOLS_SET_NAME = "External Tools"
LEGACY_EXTERNAL_TOOLS_PATH = Path("tools") / "External Tools.xml"
OPTIONS_TOOLS_PATH = Path("options") / "tools.xml"
