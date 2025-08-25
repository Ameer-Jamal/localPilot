#!/usr/bin/env python3
import sys
from PySide6.QtWidgets import QApplication
from app import App


def main():
    args = sys.argv[1:]
    sel, fname = "", ""
    for i, a in enumerate(args):
        if a == "--selection" and i + 1 < len(args): sel = args[i + 1]
        if a == "--file" and i + 1 < len(args): fname = args[i + 1]
    if not sel.strip():
        sel = sys.stdin.read()
    if not sel.strip():
        print("No selection provided.", file=sys.stderr)
        sys.exit(1)

    qapp = QApplication(sys.argv)
    win = App(sel, fname)
    win.show()
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
