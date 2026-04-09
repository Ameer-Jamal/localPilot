import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from history_presenter import (
    format_history_preview,
    format_history_source,
    format_history_title,
    format_history_updated,
)


def test_format_history_preview_defaults_and_truncates():
    assert format_history_preview("") == "No messages yet"
    assert format_history_preview("short preview") == "short preview"
    assert format_history_preview("x" * 120, max_len=20) == ("x" * 17) + "..."


def test_format_history_source_prefers_file_path():
    assert format_history_source("/tmp/demo.py", "demo.py") == "tmp/demo.py"
    assert format_history_source("", "demo.py") == "demo.py"
    assert format_history_source("", "") == "General chat"


def test_format_history_updated_humanizes_timestamp():
    assert format_history_updated("2026-04-09T10:20:30+00:00") == "2026-04-09"


def test_format_history_title_shortens_long_titles():
    assert format_history_title("Renderer jitter investigation and cleanup", "demo.py") == "Renderer jitter investiga..."
