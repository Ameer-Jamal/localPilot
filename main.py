#!/usr/bin/env python3
import sys, argparse, os
from PySide6.QtWidgets import QApplication
from app import App

def slice_by_line_col(text: str, sl: int, sc: int, el: int, ec: int) -> str:
    # JetBrains lines/cols are 1-based lines, 0-based cols in most IDEs; guard either way.
    lines = text.splitlines(keepends=True)
    n = len(lines)
    if sl < 0 or el < 0:  # no selection -> whole file
        return text
    sl = max(1, min(sl, n))     # clamp to [1..n]
    el = max(1, min(el, n))
    sc = max(0, sc)
    ec = max(0, ec)
    if (el, ec) < (sl, sc):     # empty or reversed
        return ""
    # build slice
    parts = []
    for i in range(sl, el + 1):
        line = lines[i - 1]
        if i == sl and i == el:
            parts.append(line[sc:ec])
        elif i == sl:
            parts.append(line[sc:])
        elif i == el:
            parts.append(line[:ec])
        else:
            parts.append(line)
    return "".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--filepath", default="")
    ap.add_argument("--sel-start-line", type=int, default=-1)
    ap.add_argument("--sel-start-col", type=int, default=-1)
    ap.add_argument("--sel-end-line", type=int, default=-1)
    ap.add_argument("--sel-end-col", type=int, default=-1)
    ap.add_argument("--selection", default="")  # optional manual path
    args = ap.parse_args()

    # 1) explicit --selection if provided
    sel = args.selection

    # 2) read current file
    data = ""
    if args.filepath and os.path.exists(args.filepath):
        with open(args.filepath, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()

    # 3) derive selection from line/col if not given explicitly
    if not sel and data:
        sel = slice_by_line_col(
            data,
            args.sel_start_line, args.sel_start_col,
            args.sel_end_line, args.sel_end_col
        ) or data  # fall back to whole file if empty

    if not sel.strip():
        print("No selection provided.", file=sys.stderr)
        sys.exit(1)

    app = QApplication(sys.argv)
    win = App(sel, args.file or os.path.basename(args.filepath))
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
