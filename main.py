#!/usr/bin/env python3
import os, sys, argparse
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalSocket
from app import App

SOCKET_NAME = f"ask_code_ollama_{os.getuid()}"  # per-user key

def slice_by_line_col(text: str, sl: int, sc: int, el: int, ec: int) -> str:
    lines = text.splitlines(keepends=True)
    n = len(lines)
    if sl < 0 or el < 0:
        return text
    sl = max(1, min(sl, n))
    el = max(1, min(el, n))
    sc = max(0, sc)
    ec = max(0, ec)
    if (el, ec) < (sl, sc):
        return ""
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

def try_send_to_running_instance(payload: bytes) -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if not sock.waitForConnected(150):
        return False
    sock.write(payload)
    sock.flush()
    sock.waitForBytesWritten(150)
    sock.disconnectFromServer()
    return True

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

    # Build selection text
    sel = args.selection
    data = ""
    if args.filepath and os.path.exists(args.filepath):
        with open(args.filepath, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()

    if not sel and data:
        sel = slice_by_line_col(
            data,
            args.sel_start_line, args.sel_start_col,
            args.sel_end_line, args.sel_end_col
        ) or data

    if not sel.strip():
        print("No selection provided.", file=sys.stderr)
        sys.exit(1)

    # Prepare IPC payload
    import json
    payload = json.dumps({
        "code": sel,
        "file": args.file or os.path.basename(args.filepath),
        "filepath": args.filepath,
        "cmd": "open_session"   # future-proof
    }).encode("utf-8")

    # If a window is already running, send it the new selection and exit.
    if try_send_to_running_instance(payload):
        return

    # Otherwise, start the app and begin listening for future selections.
    app = QApplication(sys.argv)
    win = App(sel, args.file or os.path.basename(args.filepath))
    win.listen_ipc(SOCKET_NAME)   # start QLocalServer
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
