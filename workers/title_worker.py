from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from config import MODEL
from ollama_client import generate_chat_title


class TitleWorker(QThread):
    done = Signal(str)

    def __init__(
            self,
            messages: list[dict[str, str]],
            *,
            model: str | None = None,
            file_name: str = "",
            file_path: str = "",
    ):
        super().__init__()
        self.messages = messages
        self.model = model or MODEL
        self.file_name = file_name
        self.file_path = file_path

    def run(self) -> None:
        title = generate_chat_title(
            self.messages,
            model=self.model,
            file_name=self.file_name,
            file_path=self.file_path,
        )
        self.done.emit(title)
