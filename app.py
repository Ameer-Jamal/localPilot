#!/usr/bin/env python3
import os, sys, argparse

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ipc import send_open_session

def _read_selection_from_ranges(path: str, sline: int, scol: int, eline: int, ecol: int) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    sline = max(1, sline); eline = max(1, eline)
    sline = min(sline, len(lines)); eline = min(eline, len(lines))
    if (eline, ecol) < (sline, scol):
        sline, eline = eline, sline
        scol, ecol = ecol, scol
    # 1-based to 0-based
    sl_i, el_i = sline - 1, eline - 1
    if sl_i == el_i:
        return lines[sl_i][scol-1:ecol-1]
    parts = [lines[sl_i][scol-1:]]
    for i in range(sl_i+1, el_i):
        parts.append(lines[i])
    parts.append(lines[el_i][:ecol-1])
    return "".join(parts)

def parse_args(argv) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--file", help="logical file label shown on tab")
    p.add_argument("--filepath", help="physical file path for range extraction")
    p.add_argument("--selection", help="pre-supplied selection text")
    p.add_argument("--sel-start-line", type=int); p.add_argument("--sel-start-col", type=int)
    p.add_argument("--sel-end-line", type=int);   p.add_argument("--sel-end-col", type=int)
    return p.parse_args(argv)

def main():
    args = parse_args(sys.argv[1:])
    label = args.file or (os.path.basename(args.filepath) if args.filepath else "selection")

    # Determine selection
    sel = (args.selection or "").rstrip("\n")
    if not sel and args.filepath and all(
        getattr(args, k) is not None for k in
        ("sel_start_line","sel_start_col","sel_end_line","sel_end_col")
    ):
        sel = _read_selection_from_ranges(
            args.filepath, args.sel_start_line, args.sel_start_col, args.sel_end_line, args.sel_end_col
        )
    if not sel and not sys.stdin.isatty():
        sel = sys.stdin.read()
    if not sel and args.filepath and os.path.exists(args.filepath):
        with open(args.filepath, "r", encoding="utf-8", errors="replace") as f:
            sel = f.read()

    if not sel.strip():
        print("No selection provided.", file=sys.stderr)
        sys.exit(1)

    # Try to hand off to an existing window (single-instance UX)
    if send_open_session(sel, label):
        return

    # Launch a new window
    qapp = QApplication(sys.argv)
    win = MainWindow(sel, label)
    win.listen_ipc()
    win.show()
    sys.exit(qapp.exec())

if __name__ == "__main__":
    main()
