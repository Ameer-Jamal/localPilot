import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from resources.html_template import load_html_template


def test_load_html_template_from_filesystem(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError
    monkeypatch.setattr('resources.html_template._res.files', boom)
    tpl = load_html_template()
    assert '<html' in tpl.lower()
