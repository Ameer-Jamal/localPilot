import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from chat_logic import (
    has_meaningful_messages,
    should_finalize_pending_assistant,
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
