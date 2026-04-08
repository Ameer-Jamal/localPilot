from __future__ import annotations

import json
import queue
import threading
from typing import Optional

import requests

from config import MODEL
from settings_store import SettingsStore


def stream_ollama(
        messages: list[dict[str, str]],
        out_q: queue.Queue,
        model: str | None = None,
        stop_event: Optional[threading.Event] = None,
) -> None:
    runtime = SettingsStore().get_runtime_settings()
    model = model or MODEL
    if not model:
        out_q.put("\n[Error] No model specified\n")
        out_q.put(None)
        return

    if stop_event and stop_event.is_set():
        out_q.put(None)
        return

    try:
        with requests.post(
            runtime.ollama_chat_url,
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "options": {
                    "temperature": runtime.temperature,
                    "num_ctx": runtime.num_ctx,
                },
                "keep_alive": runtime.keep_alive,
                "stream": True,
            },
            stream=True,
            timeout=180,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if stop_event and stop_event.is_set():
                    break
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    chunk = obj.get("message", {}).get("content", "")
                except json.JSONDecodeError:
                    chunk = line
                if chunk:
                    out_q.put(chunk)
    except Exception as e:
        out_q.put(f"\n[Error] {e}\n")
    finally:
        out_q.put(None)


def warm_up_model(model: str | None = None) -> None:
    """Issue a tiny request in the background to load the model into memory."""
    runtime = SettingsStore().get_runtime_settings()
    model = model or MODEL
    if not model:
        return

    def _warm() -> None:
        try:
            requests.post(
                runtime.ollama_chat_url,
                headers={"Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [],
                    "options": {
                        "temperature": runtime.temperature,
                        "num_ctx": runtime.num_ctx,
                    },
                    "keep_alive": runtime.keep_alive,
                    "stream": False,
                },
                timeout=30,
            ).raise_for_status()
        except Exception:
            pass

    threading.Thread(target=_warm, daemon=True).start()
