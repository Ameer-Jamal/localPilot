import json

from PySide6.QtNetwork import QLocalSocket

from ui.main_window import SOCKET_NAME


def send_open_session(code: str, file_name: str) -> bool:
    """If a window is already running, send a message to open a new tab."""
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if not sock.waitForConnected(200):
        return False
    payload = json.dumps({"cmd": "open_session", "code": code, "file": file_name}).encode("utf-8")
    sock.write(payload);
    sock.flush()
    sock.waitForBytesWritten(200)
    sock.disconnectFromServer()
    return True
