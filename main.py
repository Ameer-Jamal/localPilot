#!/usr/bin/env python3
import argparse
import os
import select
import stat
import sys
from dataclasses import dataclass

from PySide6.QtWidgets import QApplication

from history_store import HistoryStore
from ipc import send_open_session
from ui.main_window import MainWindow


# -------- file + selection utilities --------


@dataclass(frozen=True, slots=True)
class LaunchPayload:
    code: str
    display_name: str
    file_path: str

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _int_or_none(v):
    """Return int(v) or None. Treat unexpanded JetBrains macros like $SelectionStartOffset$ as None."""
    if v is None:
        return None
    s = str(v)
    if "$" in s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def slice_by_offsets(text: str, start: int, end: int) -> str:
    n = len(text)
    s = max(0, min(start, n))
    e = max(s, min(end, n))
    return text[s:e]


def slice_by_lc(text: str, s_line: int, s_col: int, e_line: int, e_col: int) -> str:
    """Lines/cols are 1-based (JetBrains). Column 1 maps to index 0."""
    lines = text.splitlines(keepends=True)
    if not lines:
        return ""

    def to_abs(line_1b: int, col_1b: int) -> int:
        L = max(1, min(int(line_1b), len(lines)))
        base = sum(len(x) for x in lines[: L - 1])
        cur = lines[L - 1]
        idx = max(0, min(int(col_1b) - 1, len(cur)))
        return base + idx

    s = to_abs(s_line, s_col)
    e = to_abs(e_line, e_col)
    if e < s:
        s, e = e, s
    return text[s:e]


def read_stdin_if_available() -> str | None:
    stream = sys.stdin
    if stream is None or stream.closed or stream.isatty():
        return None
    try:
        fd = stream.fileno()
        mode = os.fstat(fd).st_mode
    except (AttributeError, OSError, ValueError):
        return None

    # Regular redirected files are safe to read immediately.
    if stat.S_ISREG(mode):
        return stream.read()

    # Pipes and sockets should only be read when data is already available,
    # otherwise IDE consoles can block forever on startup.
    if stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode):
        try:
            ready, _, _ = select.select([stream], [], [], 0)
        except (OSError, ValueError):
            return None
        if ready:
            return stream.read()
        return None

    return None


# -------- argparse + selection resolution --------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--file")  # display name
    p.add_argument("--filepath")  # absolute path
    p.add_argument("--new-instance", action="store_true")

    # absolute offsets (accept strings; convert later to avoid argparse aborts)
    p.add_argument("--sel-start", nargs="?")
    p.add_argument("--sel-end", nargs="?")

    # line/column (1-based; accept strings; convert later)
    p.add_argument("--sel-start-line", nargs="?")
    p.add_argument("--sel-start-col", nargs="?")
    p.add_argument("--sel-end-line", nargs="?")
    p.add_argument("--sel-end-col", nargs="?")

    # raw selection text
    p.add_argument("--selection", nargs="?")
    return p.parse_args()


def get_selection(args) -> LaunchPayload:
    """Return the selection payload resolved from CLI arguments."""
    file_path = args.filepath or ""
    title = args.file or (os.path.basename(file_path) if file_path else "New Chat")

    # 1) explicit selection text
    if args.selection and "$" not in args.selection:
        return LaunchPayload(args.selection, title, file_path)

    file_text = ""
    if file_path:
        try:
            file_text = read_file(file_path)
        except OSError:
            file_text = ""

    # 2) absolute offsets
    s = _int_or_none(args.sel_start)
    e = _int_or_none(args.sel_end)
    if file_text and s is not None and e is not None:
        return LaunchPayload(slice_by_offsets(file_text, s, e), title, file_path)

    # 3) line/column
    sl = _int_or_none(args.sel_start_line)
    sc = _int_or_none(args.sel_start_col)
    el = _int_or_none(args.sel_end_line)
    ec = _int_or_none(args.sel_end_col)
    if file_text and None not in (sl, sc, el, ec):
        return LaunchPayload(slice_by_lc(file_text, sl, sc, el, ec), title, file_path)

    # 4) stdin, but only if data is actually available
    stdin_text = read_stdin_if_available()
    if stdin_text is not None:
        return LaunchPayload(stdin_text, title, file_path)

    return LaunchPayload("", title, file_path)


def should_handoff_to_existing_instance(args, payload: LaunchPayload) -> bool:
    if getattr(args, "new_instance", False):
        return False
    has_selection_payload = bool((payload.code or "").strip())
    has_file_context = bool((payload.file_path or "").strip())
    return has_selection_payload or has_file_context


# -------- entrypoint --------

def main():
    args = parse_args()
    payload = get_selection(args)

    # If an instance is running, hand off via IPC and exit.
    if should_handoff_to_existing_instance(args, payload) and send_open_session(
        payload.code,
        payload.display_name,
        payload.file_path,
    ):
        return

    # Otherwise, start the UI and begin listening for future selections.
    app = QApplication(sys.argv)
    history_store = HistoryStore()
    win = MainWindow(payload.code, payload.display_name, payload.file_path, history_store=history_store)
    win.listen_ipc()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
