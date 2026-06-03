import json
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import aws_bedrock_discovery as discovery


def test_available_aws_profiles_uses_aws_cli(monkeypatch):
    monkeypatch.setattr(discovery.shutil, "which", lambda name: "/usr/bin/aws")

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout="dev\ndefault\ndev\n", stderr="")

    monkeypatch.setattr(discovery.subprocess, "run", fake_run)
    assert discovery.available_aws_profiles() == ["dev", "default"]


def test_available_bedrock_model_ids_lists_inference_profiles(monkeypatch):
    monkeypatch.setattr(discovery.shutil, "which", lambda name: "/usr/bin/aws")
    seen = []

    def fake_run(command, **_kwargs):
        seen.append(command)
        if "list-inference-profiles" in command:
            payload = {
                "inferenceProfileSummaries": [
                    {
                        "inferenceProfileId": "profile-a",
                        "status": "ACTIVE",
                        "models": [{"modelArn": "arn:aws:bedrock:us-east-1::foundation-model/foundation-a"}],
                    },
                    {
                        "inferenceProfileId": "profile-b",
                        "status": "INACTIVE",
                        "models": [{"modelArn": "arn:aws:bedrock:us-east-1::foundation-model/foundation-b"}],
                    },
                ]
            }
        else:
            payload = {
                "modelSummaries": [
                    {
                        "modelId": "foundation-a",
                        "modelName": "Foundation A",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["TEXT"],
                        "modelLifecycle": {"status": "ACTIVE"},
                    },
                    {
                        "modelId": "foundation-b",
                        "modelName": "Foundation B",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["TEXT"],
                        "modelLifecycle": {"status": "ACTIVE"},
                    },
                ]
            }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(discovery.subprocess, "run", fake_run)
    models = discovery.available_bedrock_model_ids("dev", "us-east-1")
    assert models[0] == "profile-a"
    assert "profile-b" not in models
    assert "global.anthropic.claude-sonnet-4-6" in models
    assert any("--profile" in command for command in seen)
    assert any("list-foundation-models" in command for command in seen)


def test_available_bedrock_model_ids_falls_back_to_defaults(monkeypatch):
    monkeypatch.setattr(discovery.shutil, "which", lambda name: None)
    assert discovery.available_bedrock_model_ids("", "us-east-1") == discovery.DEFAULT_BEDROCK_MODEL_IDS


def test_discover_bedrock_model_ids_filters_non_chat_and_legacy_profiles(monkeypatch):
    monkeypatch.setattr(discovery.shutil, "which", lambda name: "/usr/bin/aws")

    def fake_run(command, **_kwargs):
        if "list-foundation-models" in command:
            payload = {
                "modelSummaries": [
                    {
                        "modelId": "anthropic.good",
                        "modelName": "Claude Good",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["TEXT"],
                        "modelLifecycle": {"status": "ACTIVE"},
                    },
                    {
                        "modelId": "cohere.embed-v4:0",
                        "modelName": "Embed v4",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["TEXT"],
                        "modelLifecycle": {"status": "ACTIVE"},
                    },
                    {
                        "modelId": "anthropic.legacy",
                        "modelName": "Legacy Claude",
                        "inputModalities": ["TEXT"],
                        "outputModalities": ["TEXT"],
                        "modelLifecycle": {"status": "LEGACY"},
                    },
                ]
            }
        else:
            payload = {
                "inferenceProfileSummaries": [
                    {
                        "inferenceProfileId": "profile-good",
                        "status": "ACTIVE",
                        "models": [{"modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.good"}],
                    },
                    {
                        "inferenceProfileId": "profile-embed",
                        "status": "ACTIVE",
                        "models": [{"modelArn": "arn:aws:bedrock:us-east-1::foundation-model/cohere.embed-v4:0"}],
                    },
                    {
                        "inferenceProfileId": "profile-legacy",
                        "status": "ACTIVE",
                        "models": [{"modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.legacy"}],
                    },
                ]
            }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(discovery.subprocess, "run", fake_run)
    result = discovery.discover_bedrock_model_ids("dev", "us-east-1")
    assert "profile-good" in result.model_ids
    assert "profile-embed" not in result.model_ids
    assert "profile-legacy" not in result.model_ids


def test_discover_bedrock_model_ids_reports_login_requirement(monkeypatch):
    monkeypatch.setattr(discovery.shutil, "which", lambda name: "/usr/bin/aws")

    def fake_run(command, **_kwargs):
        return subprocess.CompletedProcess(
            command,
            254,
            stdout="",
            stderr="An error occurred (ForbiddenException) when calling the GetRoleCredentials operation: No access",
        )

    monkeypatch.setattr(discovery.subprocess, "run", fake_run)
    result = discovery.discover_bedrock_model_ids("dev", "us-east-1")
    assert result.requires_login is True
    assert "aws sso login --profile dev" in result.status_message
    assert result.model_ids == discovery.DEFAULT_BEDROCK_MODEL_IDS


def test_login_aws_profile_reports_success(monkeypatch):
    monkeypatch.setattr(discovery.shutil, "which", lambda name: "/usr/bin/aws")

    def fake_run(command, **kwargs):
        assert kwargs["env"]["AWS_REGION"] == "us-west-2"
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(discovery.subprocess, "run", fake_run)
    success, message = discovery.login_aws_profile("dev", "us-west-2")
    assert success is True
    assert "AWS SSO login completed" in message
