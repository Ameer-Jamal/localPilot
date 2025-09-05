import importlib
import sys
import types

import pytest


def load_config(monkeypatch, get_impl):
    dummy = types.SimpleNamespace(get=get_impl)
    monkeypatch.setitem(sys.modules, 'requests', dummy)
    import config
    return importlib.reload(config)


def test_fetch_models_from_env(monkeypatch):
    cfg = load_config(monkeypatch, lambda *a, **k: None)
    monkeypatch.setenv('MODEL_LIST', 'a, b, ,c')
    assert cfg._fetch_models() == ['a', 'b', 'c']


def test_fetch_models_from_server(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {'models': [{'name': 'm1'}, {'model': 'm2'}, {}]}
    cfg = load_config(monkeypatch, lambda *a, **k: FakeResponse())
    monkeypatch.delenv('MODEL_LIST', raising=False)
    assert cfg._fetch_models() == ['m1', 'm2']


def test_fetch_models_failure(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('fail')
    cfg = load_config(monkeypatch, boom)
    monkeypatch.delenv('MODEL_LIST', raising=False)
    assert cfg._fetch_models() == []
