from __future__ import annotations

from collections.abc import Iterable


def has_meaningful_messages(messages: Iterable[dict[str, str]]) -> bool:
    return any(
        msg.get("role") != "system" and bool(msg.get("content", "").strip())
        for msg in messages
    )


def should_persist_initial_session(code: str, messages: Iterable[dict[str, str]]) -> bool:
    return bool((code or "").strip()) or has_meaningful_messages(messages)


def should_finalize_pending_assistant(assistant_md: str, assistant_persisted: bool) -> bool:
    return bool((assistant_md or "").strip()) and not assistant_persisted


def should_open_new_chat(clicked_index: int, plus_index: int) -> bool:
    return plus_index >= 0 and clicked_index == plus_index
