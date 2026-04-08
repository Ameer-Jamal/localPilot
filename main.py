#!/usr/bin/env python3
import argparse
import os
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


# -------- argparse + selection resolution --------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--file")  # display name
    p.add_argument("--filepath")  # absolute path

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
    title = args.file or (os.path.basename(file_path) if file_path else "selection")

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

    # 4) stdin
    if not sys.stdin.isatty():
        return LaunchPayload(sys.stdin.read(), title, file_path)

    return LaunchPayload("", title, file_path)


# -------- entrypoint --------

def main():
    args = parse_args()
    payload = get_selection(args)

    # If an instance is running, hand off via IPC and exit.
    if send_open_session(payload.code, payload.display_name, payload.file_path):
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
