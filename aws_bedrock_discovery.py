from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass

DEFAULT_BEDROCK_MODEL_IDS = [
    "global.anthropic.claude-sonnet-4-6",
    "us.amazon.nova-pro-v1:0",
    "us.meta.llama4-scout-17b-instruct-v1:0",
    "us.meta.llama4-maverick-17b-instruct-v1:0",
    "us.deepseek.r1-v1:0",
]

PREFERRED_BEDROCK_REGIONS = [
    "us-east-1",
    "us-west-2",
    "us-east-2",
    "us-west-1",
    "eu-west-1",
    "eu-west-2",
    "eu-central-1",
]


@dataclass(frozen=True, slots=True)
class BedrockModelDiscoveryResult:
    model_ids: list[str]
    status_message: str
    requires_login: bool = False


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def available_aws_profiles() -> list[str]:
    profiles: list[str] = []
    aws_cli = shutil.which("aws")
    if aws_cli is not None:
        try:
            completed = subprocess.run(
                [aws_cli, "configure", "list-profiles"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if completed.returncode == 0:
                profiles.extend(completed.stdout.splitlines())
        except (OSError, subprocess.SubprocessError):
            pass
    if not profiles:
        try:
            import boto3

            profiles.extend(boto3.Session().available_profiles)
        except Exception:
            pass
    return _dedupe(profiles)


def available_bedrock_regions() -> list[str]:
    regions: list[str] = []
    try:
        import boto3

        regions = boto3.session.Session().get_available_regions("bedrock-runtime")
    except Exception:
        pass
    return _dedupe([*PREFERRED_BEDROCK_REGIONS, *regions])


def _format_aws_cli_error(profile: str, region: str, stderr: str, stdout: str) -> tuple[str, bool]:
    text = (stderr or stdout or "").strip()
    selected_profile = profile.strip() or "default"
    selected_region = region.strip() or "us-east-1"
    lowered = text.lower()
    if "getrolecredentials" in lowered or "forbiddenexception" in lowered or "sso" in lowered:
        return (
            f"AWS profile '{selected_profile}' is not logged in or lacks access. "
            f"Run `aws sso login --profile {selected_profile}` and verify Bedrock access in {selected_region}.",
            True,
        )
    if text:
        return (text, False)
    return ("AWS CLI could not list Bedrock models.", False)


def _foundation_model_id_from_arn(model_arn: str) -> str:
    marker = "foundation-model/"
    if marker not in model_arn:
        return ""
    return model_arn.split(marker, 1)[1].strip()


def _is_chat_model_summary(summary: dict) -> bool:
    model_id = str(summary.get("modelId") or "").strip().lower()
    model_name = str(summary.get("modelName") or "").strip().lower()
    lifecycle = summary.get("modelLifecycle") or {}
    lifecycle_status = str(lifecycle.get("status") or "").upper()
    input_modalities = {str(value).upper() for value in summary.get("inputModalities", [])}
    output_modalities = {str(value).upper() for value in summary.get("outputModalities", [])}
    blocked_keywords = {
        "embed",
        "rerank",
        "upscale",
        "inpaint",
        "outpaint",
        "erase",
        "remove-background",
        "search-replace",
        "search-recolor",
        "style-transfer",
        "style-guide",
        "control-sketch",
        "control-structure",
    }
    if lifecycle_status != "ACTIVE":
        return False
    if "TEXT" not in input_modalities or "TEXT" not in output_modalities:
        return False
    return not any(keyword in model_id or keyword in model_name for keyword in blocked_keywords)


def _foundation_model_summaries(profile: str, profile_args: list[str], region: str, aws_cli: str) -> tuple[dict[str, dict], str]:
    command = [
        aws_cli,
        "bedrock",
        "list-foundation-models",
        "--by-output-modality",
        "TEXT",
        "--region",
        region.strip(),
        "--output",
        "json",
        "--no-cli-pager",
    ]
    command.extend(profile_args)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            message, _login_required = _format_aws_cli_error(profile, region, completed.stderr, completed.stdout)
            return {}, message
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
        summaries = payload.get("modelSummaries", [])
        lookup: dict[str, dict] = {}
        if isinstance(summaries, list):
            for summary in summaries:
                if not isinstance(summary, dict):
                    continue
                model_id = str(summary.get("modelId") or "").strip()
                if model_id:
                    lookup[model_id] = summary
        return lookup, ""
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}, "Failed to query Bedrock foundation models from AWS CLI."


def discover_bedrock_model_ids(profile: str, region: str) -> BedrockModelDiscoveryResult:
    model_ids: list[str] = []
    status_messages: list[str] = []
    requires_login = False
    aws_cli = shutil.which("aws")
    if aws_cli is None:
        return BedrockModelDiscoveryResult(
            model_ids=list(DEFAULT_BEDROCK_MODEL_IDS),
            status_message="AWS CLI was not found. Showing starter Bedrock models only.",
            requires_login=False,
        )
    if not region.strip():
        return BedrockModelDiscoveryResult(
            model_ids=list(DEFAULT_BEDROCK_MODEL_IDS),
            status_message="Choose an AWS region to load Bedrock models.",
            requires_login=False,
        )
    if aws_cli is not None and region.strip():
        profile_args = []
        if profile.strip() and profile.strip() != "default":
            profile_args = ["--profile", profile.strip()]
        foundation_lookup, foundation_error = _foundation_model_summaries(profile, profile_args, region, aws_cli)
        if foundation_error:
            status_messages.append(foundation_error)
        command = [
            aws_cli,
            "bedrock",
            "list-inference-profiles",
            "--region",
            region.strip(),
            "--output",
            "json",
            "--no-cli-pager",
        ]
        command.extend(profile_args)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                payload = json.loads(completed.stdout)
                summaries = payload.get("inferenceProfileSummaries", [])
                if isinstance(summaries, list):
                    for summary in summaries:
                        if not isinstance(summary, dict):
                            continue
                        profile_id = summary.get("inferenceProfileId")
                        status = str(summary.get("status") or "").upper()
                        models = summary.get("models", [])
                        foundation_ids = [
                            _foundation_model_id_from_arn(str(model.get("modelArn") or ""))
                            for model in models
                            if isinstance(model, dict)
                        ]
                        foundation_summaries = [
                            foundation_lookup[foundation_id]
                            for foundation_id in foundation_ids
                            if foundation_id in foundation_lookup
                        ]
                        is_chat_profile = any(_is_chat_model_summary(item) for item in foundation_summaries)
                        if isinstance(profile_id, str) and profile_id and status in {"ACTIVE", ""} and is_chat_profile:
                            model_ids.append(profile_id)
            elif completed.returncode != 0:
                message, login_required = _format_aws_cli_error(profile, region, completed.stderr, completed.stdout)
                status_messages.append(message)
                requires_login = requires_login or login_required
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            status_messages.append("Failed to query Bedrock inference profiles from AWS CLI.")
    return BedrockModelDiscoveryResult(
        model_ids=_dedupe([*model_ids, *DEFAULT_BEDROCK_MODEL_IDS]),
        status_message=status_messages[0] if status_messages else (
            f"Loaded chat-capable Bedrock inference profiles for {(profile.strip() or 'default')} in {region.strip()}."
        ),
        requires_login=requires_login,
    )


def available_bedrock_model_ids(profile: str, region: str) -> list[str]:
    return discover_bedrock_model_ids(profile, region).model_ids


def login_aws_profile(profile: str, region: str) -> tuple[bool, str]:
    aws_cli = shutil.which("aws")
    selected_profile = profile.strip() or "default"
    selected_region = region.strip() or "us-east-1"
    if aws_cli is None:
        return False, "AWS CLI was not found."

    command = [aws_cli, "sso", "login", "--profile", selected_profile]
    env = None
    if selected_region:
        env = {
            **os.environ,
            "AWS_REGION": selected_region,
            "AWS_DEFAULT_REGION": selected_region,
        }
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if completed.returncode != 0:
        message, _requires_login = _format_aws_cli_error(profile, region, completed.stderr, completed.stdout)
        return False, message
    return True, f"AWS SSO login completed for {selected_profile}."
