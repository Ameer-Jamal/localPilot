from __future__ import annotations

import queue
import threading
from typing import Any

from ollama_client import build_title_messages, normalize_chat_title
from settings_store import RuntimeSettings, SettingsStore


class BedrockClientError(RuntimeError):
    pass


def _bedrock_session(profile: str, region: str):
    try:
        import boto3
    except ModuleNotFoundError as exc:
        raise BedrockClientError(
            "AWS Bedrock support requires boto3. Install dependencies with `pip install -r requirements.txt`."
        ) from exc

    kwargs: dict[str, str] = {}
    if profile:
        kwargs["profile_name"] = profile
    if region:
        kwargs["region_name"] = region
    return boto3.Session(**kwargs)


def _split_system_messages(messages: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    system_text: list[str] = []
    converse_messages: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_text.append(content)
            continue
        converse_role = "assistant" if role == "assistant" else "user"
        converse_messages.append(
            {
                "role": converse_role,
                "content": [{"text": content}],
            }
        )
    system = [{"text": "\n\n".join(system_text)}] if system_text else []
    return converse_messages, system


def _format_bedrock_exception(exc: Exception, runtime: RuntimeSettings) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()
    profile = runtime.bedrock_aws_profile or "default"
    region = runtime.bedrock_aws_region or "us-east-1"
    if "getrolecredentials" in lowered or "forbiddenexception" in lowered or "sso" in lowered:
        return (
            f"AWS profile '{profile}' is not logged in or lacks Bedrock access in {region}. "
            f"Run `aws sso login --profile {profile}` and verify the profile can use Bedrock."
        )
    return message


def _bedrock_inference_config(runtime: RuntimeSettings, *, max_tokens: int | None = None) -> dict[str, Any]:
    return {
        "maxTokens": runtime.bedrock_max_tokens if max_tokens is None else max_tokens,
    }


def converse_bedrock_raw(
        messages: list[dict[str, str]],
        *,
        model_id: str,
        runtime: RuntimeSettings | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
) -> dict[str, Any]:
    runtime = runtime or SettingsStore().get_runtime_settings()
    if not model_id:
        raise BedrockClientError("No Bedrock model specified")
    converse_messages, system = _split_system_messages(messages)
    if not converse_messages:
        raise BedrockClientError("No messages to send to Bedrock")

    session = _bedrock_session(runtime.bedrock_aws_profile, runtime.bedrock_aws_region)
    client = session.client("bedrock-runtime", region_name=runtime.bedrock_aws_region)
    payload: dict[str, Any] = {
        "modelId": model_id,
        "messages": converse_messages,
        "inferenceConfig": _bedrock_inference_config(runtime, max_tokens=max_tokens),
    }
    if system:
        payload["system"] = system
    return client.converse(**payload)


def extract_converse_text(raw_response: dict[str, Any]) -> str:
    content = raw_response.get("output", {}).get("message", {}).get("content", [])
    text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
    response_text = "\n".join(part for part in text_parts if part).strip()
    if not response_text:
        raise BedrockClientError("Bedrock response did not contain text output")
    return response_text


def stream_bedrock(
        messages: list[dict[str, str]],
        out_q: queue.Queue,
        model_id: str,
        stop_event: threading.Event | None = None,
) -> None:
    runtime = SettingsStore().get_runtime_settings()
    if stop_event and stop_event.is_set():
        out_q.put(None)
        return
    try:
        response_text = extract_converse_text(
            converse_bedrock_raw(messages, model_id=model_id, runtime=runtime)
        )
        if not (stop_event and stop_event.is_set()):
            out_q.put(response_text)
    except Exception as exc:
        out_q.put(f"\n[Error] {_format_bedrock_exception(exc, runtime)}\n")
    finally:
        out_q.put(None)


def generate_bedrock_chat_title(
        messages: list[dict[str, str]],
        *,
        model_id: str,
        file_name: str = "",
        file_path: str = "",
) -> str:
    title_messages = build_title_messages(messages, file_name=file_name, file_path=file_path)
    if not model_id or not title_messages:
        return ""
    runtime = SettingsStore().get_runtime_settings()
    try:
        response_text = extract_converse_text(
            converse_bedrock_raw(
                title_messages,
                model_id=model_id,
                runtime=runtime,
                max_tokens=min(runtime.bedrock_max_tokens, 256),
            )
        )
    except Exception:
        return ""
    return normalize_chat_title(response_text)
