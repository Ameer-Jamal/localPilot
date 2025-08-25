import json
import requests
from PySide6.QtCore import QThread, Signal
from config import MODEL, TEMP, OLLAMA_CHAT_URL, NUM_CTX, KEEP_ALIVE

class ChatWorker(QThread):
    """Streams tokens from Ollama /api/chat and emits chunks into the UI."""
    chunk = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, messages: list[dict]):
        super().__init__()
        self.messages = messages

    def run(self):
        try:
            with requests.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": MODEL,
                    "messages": self.messages,
                    "options": {
                        "temperature": float(TEMP),
                        "num_ctx": int(NUM_CTX),
                    },
                    "keep_alive": str(KEEP_ALIVE),
                    "stream": True,
                },
                stream=True,
                timeout=(10, 600),
            ) as r:
                try:
                    r.raise_for_status()
                except requests.HTTPError:
                    self.error.emit(f"HTTP {r.status_code}: {r.text}")
                    return

                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        msg = obj.get("message") or {}
                        txt = msg.get("content", "") or obj.get("response", "")
                    except json.JSONDecodeError:
                        txt = line
                    if txt:
                        self.chunk.emit(txt)
        except requests.exceptions.RequestException as e:
            self.error.emit(f"Network error: {e}")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.done.emit()