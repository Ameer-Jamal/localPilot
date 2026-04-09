import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from chat_logic import (
    has_meaningful_messages,
    pick_preferred_model,
    should_finalize_pending_assistant,
    should_handle_worker_signal,
    should_open_new_chat,
    should_persist_initial_session,
)


def test_has_meaningful_messages_ignores_system_only_history():
    assert not has_meaningful_messages([
        {"role": "system", "content": "You are helpful."},
        {"role": "system", "content": "Pinned code"},
    ])


def test_has_meaningful_messages_detects_real_chat_content():
    assert has_meaningful_messages([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Explain this flow"},
    ])


def test_should_open_new_chat_only_for_plus_tab_click():
    assert should_open_new_chat(3, 3)
    assert not should_open_new_chat(2, 3)
    assert not should_open_new_chat(0, -1)


def test_should_persist_initial_session_only_when_chat_has_content():
    assert not should_persist_initial_session("", [{"role": "system", "content": "Base prompt"}])
    assert should_persist_initial_session("class Demo {}", [{"role": "system", "content": "Base prompt"}])
    assert should_persist_initial_session("", [{"role": "user", "content": "Help me debug this"}])


def test_should_finalize_pending_assistant_only_for_unpersisted_content():
    assert should_finalize_pending_assistant("final answer", False)
    assert not should_finalize_pending_assistant("", False)
    assert not should_finalize_pending_assistant("final answer", True)


def test_pick_preferred_model_prioritizes_session_then_saved_then_default():
    available = ["gemma3:12b", "qwen2.5-coder:7b", "llama3"]
    assert pick_preferred_model(available, session_model="llama3", saved_model="gemma3:12b", default_model="qwen2.5-coder:7b") == "llama3"
    assert pick_preferred_model(available, session_model="", saved_model="gemma3:12b", default_model="qwen2.5-coder:7b") == "gemma3:12b"
    assert pick_preferred_model(available, session_model="", saved_model="", default_model="qwen2.5-coder:7b") == "qwen2.5-coder:7b"
    assert pick_preferred_model(available, session_model="", saved_model="missing", default_model="also-missing") == "gemma3:12b"


def test_should_handle_worker_signal_only_accepts_active_worker_sender():
    current = object()
    stale = object()
    assert should_handle_worker_signal(current, current)
    assert should_handle_worker_signal(current, None)
    assert not should_handle_worker_signal(current, stale)
    assert not should_handle_worker_signal(None, stale)
