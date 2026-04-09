from __future__ import annotations

import json
import queue
import threading
from typing import Optional

import requests

from config import MODEL
from settings_store import SettingsStore


def _non_system_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {"role": msg.get("role", "user"), "content": msg.get("content", "").strip()}
        for msg in messages
        if msg.get("role") != "system" and msg.get("content", "").strip()
    ]


def normalize_chat_title(raw: str) -> str:
    title = " ".join((raw or "").replace("\n", " ").split()).strip(" \"'`#*:-")
    if not title:
        return ""
    if ":" in title:
        head = title.split(":", 1)[0].strip()
        if len(head.split()) >= 2:
            title = head
    words = title.split()
    if len(words) > 6:
        title = " ".join(words[:6])
    return title[:60].strip()


def build_title_messages(
        messages: list[dict[str, str]],
        *,
        file_name: str = "",
        file_path: str = "",
) -> list[dict[str, str]]:
    context = _non_system_messages(messages)[-2:]
    if not context:
        return []
    source = file_path or file_name or "General chat"
    prompt = (
        "Generate a concise title for this chat.\n"
        "Rules:\n"
        "- 2 to 4 words.\n"
        "- Plain text only.\n"
        "- Give just enough context to recognize the topic.\n"
        "- No quotes, markdown, prefixes, trailing punctuation, or filler words like chat/conversation/help.\n"
        f"- Source context: {source}."
    )
    return [{"role": "system", "content": prompt}, *context]


def generate_chat_title(
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        file_name: str = "",
        file_path: str = "",
) -> str:
    runtime = SettingsStore().get_runtime_settings()
    model = MODEL if model is None else model
    title_messages = build_title_messages(messages, file_name=file_name, file_path=file_path)
    if not model or not title_messages:
        return ""
    try:
        response = requests.post(
            runtime.ollama_chat_url,
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": title_messages,
                "options": {
                    "temperature": 0.1,
                    "num_ctx": min(runtime.num_ctx, 1024),
                },
                "keep_alive": runtime.keep_alive,
                "stream": False,
            },
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return ""
    content = payload.get("message", {}).get("content", "")
    return normalize_chat_title(content)


def stream_ollama(
        messages: list[dict[str, str]],
        out_q: queue.Queue,
        model: str | None = None,
        stop_event: Optional[threading.Event] = None,
) -> None:
    runtime = SettingsStore().get_runtime_settings()
    model = MODEL if model is None else model
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
    model = MODEL if model is None else model
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
