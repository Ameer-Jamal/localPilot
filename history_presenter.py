from __future__ import annotations

from pathlib import Path


def _ellipsis(text: str, max_len: int) -> str:
    cleaned = " ".join((text or "").split()).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3].rstrip()}..."


def format_history_preview(preview: str, max_len: int = 90) -> str:
    cleaned = " ".join((preview or "").split()).strip()
    if not cleaned:
        return "No messages yet"
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3].rstrip()}..."


def format_history_source(file_path: str, file_name: str) -> str:
    if file_path:
        path = Path(file_path)
        tail = "/".join(path.parts[-2:]) if len(path.parts) >= 2 else path.name
        return _ellipsis(tail or path.name, 34)
    if file_name:
        return _ellipsis(file_name, 34)
    return "General chat"


def format_history_updated(updated_at: str) -> str:
    return (updated_at or "").split("T", 1)[0]


def format_history_title(title: str, file_name: str) -> str:
    return _ellipsis(title or file_name or "Untitled Chat", 28)
