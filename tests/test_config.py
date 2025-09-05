import importlib
import sys
import types

import pytest


def load_config(monkeypatch, get_impl):
    dummy = types.SimpleNamespace(get=get_impl)
    monkeypatch.setitem(sys.modules, 'requests', dummy)
    if 'config' in sys.modules:
        del sys.modules['config']
    import config
    return config


def test_fetch_ollama_models_from_env(monkeypatch):
    monkeypatch.setenv('MODEL_LIST', 'a, b, ,c')
    cfg = load_config(monkeypatch, lambda *a, **k: None)
    assert cfg.fetch_ollama_models() == ['a', 'b', 'c']


def test_fetch_ollama_models_from_server(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {'models': [{'name': 'm1'}, {'model': 'm2'}, {}]}

    monkeypatch.delenv('MODEL_LIST', raising=False)
    cfg = load_config(monkeypatch, lambda *a, **k: FakeResponse())
    assert cfg.fetch_ollama_models() == ['m1', 'm2']


def test_fetch_ollama_models_failure(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('fail')

    monkeypatch.delenv('MODEL_LIST', raising=False)
    cfg = load_config(monkeypatch, boom)
    assert cfg.fetch_ollama_models() == []


def test_config_initial_model_list_and_model(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {'models': [{'name': 'initial_model1'}, {'model': 'initial_model2'}]}

    monkeypatch.delenv('MODEL_LIST', raising=False)
    cfg = load_config(monkeypatch, lambda *a, **k: FakeResponse())
    assert cfg.MODEL_LIST == ['initial_model1', 'initial_model2']
    assert cfg.MODEL == 'initial_model1'


def test_config_initial_no_model(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {'models': []}

    monkeypatch.delenv('MODEL_LIST', raising=False)
    cfg = load_config(monkeypatch, lambda *a, **k: FakeResponse())
    assert cfg.MODEL_LIST == []
    assert cfg.MODEL == []
