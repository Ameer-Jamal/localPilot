from __future__ import annotations

import queue
import threading
from PySide6.QtCore import QThread, Signal

from config import MODEL
from ollama_client import stream_ollama


class ChatWorker(QThread):
    """Streams tokens from Ollama /api/chat and emits chunks into the UI."""
    chunk = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, messages: list[dict], model: str | None = None):
        super().__init__()
        self.messages = messages
        self.model = model or MODEL
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Request the worker to stop streaming."""
        self._stop_event.set()

    def _build_prompt(self) -> str:
        parts: list[str] = []
        for msg in self.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(content)
            else:
                parts.append(f"{role}: {content}")
        parts.append("assistant:")
        return "\n".join(parts)

    def run(self):
        prompt = self._build_prompt()
        q: queue.Queue[str | None] = queue.Queue()

        def worker() -> None:
            stream_ollama(prompt, q, model=self.model, stop_event=self._stop_event)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        try:
            while True:
                try:
                    chunk = q.get(timeout=0.1)
                except queue.Empty:
                    if self._stop_event.is_set():
                        break
                    continue
                if chunk is None:
                    break
                if chunk.startswith("[Error]") or chunk.startswith("\n[Error]"):
                    self.error.emit(chunk.strip())
                else:
                    self.chunk.emit(chunk)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._stop_event.set()
            t.join()
            self.done.emit()
