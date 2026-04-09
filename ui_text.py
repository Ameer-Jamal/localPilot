from __future__ import annotations

from app_constants import HISTORY_LABEL, NEW_CHAT_TITLE, SETTINGS_LABEL, SHOW_HISTORY_LABEL

LABEL_MODEL = "Model"
LABEL_HISTORY = HISTORY_LABEL
LABEL_UNTITLED_CHAT = "Untitled Chat"
LABEL_STANDARD_WINDOW = "Standard Window"
LABEL_ALWAYS_ON_TOP = "Always on Top"
LABEL_SAVED_CHATS = "Saved Chats"
LABEL_OPEN = "Open"
LABEL_REOPEN = "Reopen"
LABEL_OPEN_SELECTED = "Open Selected"
LABEL_DELETE = "Delete"
LABEL_REFRESH = "Refresh"
LABEL_START_OLLAMA = "Start Ollama"
LABEL_STOP_OLLAMA = "Stop Ollama"
LABEL_INSTALL_MODEL = "Install Model"
LABEL_SEND = "Send"
LABEL_STOP = "Stop"
LABEL_CANCEL = "Cancel"
LABEL_CLEAR_HISTORY = "Clear History"
LABEL_CLOSE_TAB = "Close Tab"
LABEL_KEEP_OPEN = "Keep Open"

TOOLTIP_KEEP_ON_TOP = "Keep window on top"
TOOLTIP_ALWAYS_ON_TOP_STATUS = "Always-on-top status"
TOOLTIP_SHOW_HISTORY = "Show saved chats"
TOOLTIP_SHOW_HISTORY_PANEL = "Show history panel"
TOOLTIP_HIDE_HISTORY_PANEL = "Hide history panel"
TOOLTIP_OPEN_SETTINGS = "Open LocalPilot settings"
TOOLTIP_NEW_CHAT_TAB = "New chat"

STATUS_READY = "Ready"
STATUS_SERVER_NOT_RUNNING = "Ollama server not running. Click Run Ollama to start it."
STATUS_SERVER_STARTING = "Ollama server starting…"
STATUS_STOPPED_OLLAMA = "Stopped Ollama started by LocalPilot"
STATUS_NO_OLLAMA_TO_STOP = "No LocalPilot-managed Ollama process or loaded models to stop"
STATUS_FAILED_TO_STOP_OLLAMA = "Failed to stop Ollama cleanly"
STATUS_NO_MODELS_AVAILABLE = "No Ollama models available to chat with."
STATUS_GENERATION_STOPPED = "Generation stopped"

EMPTY_STATE_TITLE = "Start a new chat"
EMPTY_STATE_BODY = "Open a blank chat, review saved conversations, or adjust LocalPilot settings before you begin."
EMPTY_STATE_META = "Works with or without a pinned code selection."
HISTORY_PANEL_BODY = "Reopen previous chats or remove history you no longer need."

CONFIRM_CLEAR_HISTORY_TITLE = "Clear Saved History"
CONFIRM_CLEAR_HISTORY_TEXT = "Clear all saved chat history?"
CONFIRM_CLEAR_HISTORY_INFO = (
    "This permanently deletes every saved chat. Open tabs will remain visible until you close them."
)
CONFIRM_DELETE_HISTORY_TITLE = "Delete Chat History"
CONFIRM_DELETE_HISTORY_INFO = "This permanently removes the saved chat transcript from LocalPilot."
CONFIRM_CLOSE_CHAT_TITLE = "Close Chat"
CONFIRM_CLOSE_CHAT_INFO = "You can open a new blank chat from the + tab."


def status_no_models_found(default_pull_model: str) -> str:
    return (
        f"No Ollama models found. Install one with `ollama pull {default_pull_model}` "
        f"or click {LABEL_INSTALL_MODEL}."
    )


def status_failed_to_start_ollama(exc: Exception) -> str:
    return f"Failed to start Ollama: {exc}"


def status_released_models(count: int) -> str:
    noun = "model" if count == 1 else "models"
    return (
        f"Released {count} loaded {noun}. Ollama is still running because it was not started by LocalPilot."
    )


def status_installing_model(model: str) -> str:
    return f"Installing {model}…"


def status_failed_to_install_model(exc: Exception) -> str:
    return f"Failed to install model: {exc}"


def status_generating(model: str) -> str:
    return f"Generating with {model}…"


def status_done(elapsed: float, chars: int, cps: int, model: str) -> str:
    return f"Done in {elapsed:.1f}s | {chars} chars @ {cps} cps | {model}"


def confirm_delete_history_text(title: str) -> str:
    return f'Delete "{title or LABEL_UNTITLED_CHAT}" from history?'


def confirm_close_chat_text(title: str) -> str:
    return f'Close "{title}"?'


def history_count_text(count: int) -> str:
    return f"{count} saved chats"


__all__ = [
    "CONFIRM_CLEAR_HISTORY_INFO",
    "CONFIRM_CLEAR_HISTORY_TEXT",
    "CONFIRM_CLEAR_HISTORY_TITLE",
    "CONFIRM_CLOSE_CHAT_INFO",
    "CONFIRM_CLOSE_CHAT_TITLE",
    "CONFIRM_DELETE_HISTORY_INFO",
    "CONFIRM_DELETE_HISTORY_TITLE",
    "EMPTY_STATE_BODY",
    "EMPTY_STATE_META",
    "EMPTY_STATE_TITLE",
    "HISTORY_LABEL",
    "HISTORY_PANEL_BODY",
    "LABEL_ALWAYS_ON_TOP",
    "LABEL_CANCEL",
    "LABEL_CLEAR_HISTORY",
    "LABEL_CLOSE_TAB",
    "LABEL_DELETE",
    "LABEL_HISTORY",
    "LABEL_INSTALL_MODEL",
    "LABEL_KEEP_OPEN",
    "LABEL_MODEL",
    "LABEL_OPEN",
    "LABEL_OPEN_SELECTED",
    "LABEL_REFRESH",
    "LABEL_REOPEN",
    "LABEL_SAVED_CHATS",
    "LABEL_SEND",
    "LABEL_STANDARD_WINDOW",
    "LABEL_START_OLLAMA",
    "LABEL_STOP",
    "LABEL_STOP_OLLAMA",
    "LABEL_UNTITLED_CHAT",
    "NEW_CHAT_TITLE",
    "SETTINGS_LABEL",
    "SHOW_HISTORY_LABEL",
    "STATUS_FAILED_TO_STOP_OLLAMA",
    "STATUS_GENERATION_STOPPED",
    "STATUS_NO_MODELS_AVAILABLE",
    "STATUS_NO_OLLAMA_TO_STOP",
    "STATUS_READY",
    "STATUS_SERVER_NOT_RUNNING",
    "STATUS_SERVER_STARTING",
    "STATUS_STOPPED_OLLAMA",
    "TOOLTIP_ALWAYS_ON_TOP_STATUS",
    "TOOLTIP_HIDE_HISTORY_PANEL",
    "TOOLTIP_KEEP_ON_TOP",
    "TOOLTIP_NEW_CHAT_TAB",
    "TOOLTIP_OPEN_SETTINGS",
    "TOOLTIP_SHOW_HISTORY",
    "TOOLTIP_SHOW_HISTORY_PANEL",
    "confirm_close_chat_text",
    "confirm_delete_history_text",
    "history_count_text",
    "status_done",
    "status_failed_to_install_model",
    "status_failed_to_start_ollama",
    "status_generating",
    "status_installing_model",
    "status_no_models_found",
    "status_released_models",
]
