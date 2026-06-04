from __future__ import annotations

import queue
import threading

from bedrock_client import generate_bedrock_chat_title, stream_bedrock
from config import MODEL
from ollama_client import generate_chat_title, stream_ollama, warm_up_model
from settings_store import RuntimeSettings

BEDROCK_PREFIX = "bedrock:"
BEDROCK_LABEL_PREFIX = "Bedrock: "


def bedrock_model_key(model_id: str) -> str:
    return f"{BEDROCK_PREFIX}{model_id.strip()}"


def is_bedrock_model(model: str) -> bool:
    return (model or "").strip().startswith(BEDROCK_PREFIX)


def provider_model_id(model: str) -> str:
    cleaned = (model or "").strip()
    if is_bedrock_model(cleaned):
        return cleaned[len(BEDROCK_PREFIX):].strip()
    return cleaned


def display_model_name(model: str) -> str:
    if is_bedrock_model(model):
        return f"{BEDROCK_LABEL_PREFIX}{provider_model_id(model)}"
    return model


def available_bedrock_models(runtime: RuntimeSettings) -> list[str]:
    if not runtime.bedrock_enabled:
        return []
    return [bedrock_model_key(model_id) for model_id in runtime.bedrock_model_ids if model_id.strip()]


def stream_model(
        messages: list[dict[str, str]],
        out_q: queue.Queue,
        *,
        model: str | None = None,
        stop_event: threading.Event | None = None,
) -> None:
    selected = MODEL if model is None else (model or "").strip()
    if is_bedrock_model(selected):
        stream_bedrock(messages, out_q, model_id=provider_model_id(selected), stop_event=stop_event)
        return
    stream_ollama(messages, out_q, model=selected, stop_event=stop_event)


def generate_model_chat_title(
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        file_name: str = "",
        file_path: str = "",
) -> str:
    selected = MODEL if model is None else (model or "").strip()
    if is_bedrock_model(selected):
        return generate_bedrock_chat_title(
            messages,
            model_id=provider_model_id(selected),
            file_name=file_name,
            file_path=file_path,
        )
    return generate_chat_title(
        messages,
        model=selected,
        file_name=file_name,
        file_path=file_path,
    )


def warm_up_selected_model(model: str | None = None) -> None:
    selected = MODEL if model is None else (model or "").strip()
    if not selected or is_bedrock_model(selected):
        return
    warm_up_model(selected)
