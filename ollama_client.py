from __future__ import annotations

import json
import queue
import threading
from typing import Optional

import requests

from config import MODEL, OLLAMA_BASE_URL, TEMP

OLLAMA_URL = f"{OLLAMA_BASE_URL}/generate"


def stream_ollama(prompt: str, out_q: queue.Queue, model: str | None = None,
                  stop_event: Optional[threading.Event] = None) -> None:
    model = model or MODEL
    if not model:
        out_q.put("\n[Error] No model specified\n")
        out_q.put(None)
        return

    if stop_event and stop_event.is_set():
        out_q.put(None)
        return

    print(f"[stream_ollama] requesting model={model}")
    try:
        with requests.post(
                OLLAMA_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps({
                    "model": model,
                    "prompt": prompt,
                    "options": {"temperature": TEMP},
                    "stream": True,
                }),
                stream=True,
                timeout=180,
        ) as r:
            r.raise_for_status()
            confirmed = False
            for line in r.iter_lines(decode_unicode=True):
                if stop_event and stop_event.is_set():
                    break
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if not confirmed and obj.get("model"):
                        print(f"[stream_ollama] server model={obj['model']}")
                        confirmed = True
                    chunk = obj.get("response", "")
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
    model = model or MODEL
    if not model:
        return

    def _warm() -> None:
        try:
            requests.post(
                OLLAMA_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps({"model": model, "prompt": "", "stream": False}),
                timeout=30,
            ).raise_for_status()
        except Exception:
            pass

    threading.Thread(target=_warm, daemon=True).start()
