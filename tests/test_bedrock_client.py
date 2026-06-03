import importlib
import queue
import sys
import types
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))


def load_bedrock_client(monkeypatch):
    sys.modules.pop("bedrock_client", None)
    sys.modules.pop("ollama_client", None)
    settings_mod = types.ModuleType("settings_store")
    settings_mod.RuntimeSettings = object
    settings_mod.SettingsStore = lambda: types.SimpleNamespace(
        get_runtime_settings=lambda: types.SimpleNamespace(
            bedrock_aws_profile="dev",
            bedrock_aws_region="us-east-1",
            temperature=0.2,
            bedrock_max_tokens=4096,
            ollama_chat_url="http://localhost:11434/api/chat",
            keep_alive="10m",
            num_ctx=16384,
        )
    )
    monkeypatch.setitem(sys.modules, "settings_store", settings_mod)
    import bedrock_client
    return importlib.reload(bedrock_client)


def test_converse_bedrock_raw_builds_payload(monkeypatch):
    seen = {}

    class FakeClient:
        def converse(self, **payload):
            seen["payload"] = payload
            return {"output": {"message": {"content": [{"text": "hi"}]}}}

    class FakeSession:
        def __init__(self, **kwargs):
            seen["session"] = kwargs

        def client(self, service, region_name=None):
            seen["client"] = (service, region_name)
            return FakeClient()

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(Session=FakeSession))
    client = load_bedrock_client(monkeypatch)
    runtime = types.SimpleNamespace(
        bedrock_aws_profile="dev",
        bedrock_aws_region="us-west-2",
        temperature=0.4,
        bedrock_max_tokens=1234,
    )

    raw = client.converse_bedrock_raw(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "there"},
        ],
        model_id="model-a",
        runtime=runtime,
    )

    assert raw["output"]["message"]["content"][0]["text"] == "hi"
    assert seen["session"] == {"profile_name": "dev", "region_name": "us-west-2"}
    assert seen["client"] == ("bedrock-runtime", "us-west-2")
    assert seen["payload"]["modelId"] == "model-a"
    assert seen["payload"]["system"] == [{"text": "sys"}]
    assert seen["payload"]["messages"][0] == {"role": "user", "content": [{"text": "hello"}]}
    assert seen["payload"]["messages"][1] == {"role": "assistant", "content": [{"text": "there"}]}
    assert seen["payload"]["inferenceConfig"] == {"maxTokens": 1234}


def test_stream_bedrock_emits_text_and_done(monkeypatch):
    client = load_bedrock_client(monkeypatch)
    monkeypatch.setattr(
        client,
        "converse_bedrock_raw",
        lambda *a, **k: {"output": {"message": {"content": [{"text": "answer"}]}}},
    )
    q = queue.Queue()
    client.stream_bedrock([{"role": "user", "content": "hello"}], q, "model-a")
    assert q.get() == "answer"
    assert q.get() is None


def test_stream_bedrock_emits_error_and_done(monkeypatch):
    client = load_bedrock_client(monkeypatch)

    def boom(*_args, **_kwargs):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(client, "converse_bedrock_raw", boom)
    q = queue.Queue()
    client.stream_bedrock([{"role": "user", "content": "hello"}], q, "model-a")
    assert q.get().startswith("\n[Error]")
    assert q.get() is None


def test_missing_boto3_error_is_actionable(monkeypatch):
    client = load_bedrock_client(monkeypatch)
    monkeypatch.delitem(sys.modules, "boto3", raising=False)

    class MissingBoto3Finder:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "boto3":
                raise ModuleNotFoundError("No module named 'boto3'")
            return None

    sys.meta_path.insert(0, MissingBoto3Finder())
    try:
        try:
            client._bedrock_session("", "us-east-1")
        except client.BedrockClientError as exc:
            assert "pip install -r requirements.txt" in str(exc)
        else:
            raise AssertionError("Expected BedrockClientError")
    finally:
        sys.meta_path.pop(0)


def test_stream_bedrock_rewrites_sso_forbidden_error(monkeypatch):
    client = load_bedrock_client(monkeypatch)

    def boom(*_args, **_kwargs):
        raise RuntimeError(
            "An error occurred (ForbiddenException) when calling the GetRoleCredentials operation: No access"
        )

    monkeypatch.setattr(client, "converse_bedrock_raw", boom)
    q = queue.Queue()
    client.stream_bedrock([{"role": "user", "content": "hello"}], q, "model-a")
    assert "aws sso login --profile dev" in q.get()
    assert q.get() is None
