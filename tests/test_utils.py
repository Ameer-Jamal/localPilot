import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils import lang_hint, build_prompt


def test_lang_hint_known_extensions():
    assert lang_hint('example.py') == 'python'
    assert lang_hint('script.JS') == 'javascript'
    assert lang_hint('style.CSS') == 'css'


def test_lang_hint_default_plaintext():
    assert lang_hint('unknown.ext') == 'plaintext'
    assert lang_hint('') == 'plaintext'


def test_build_prompt_includes_task_code_and_lang():
    prompt = build_prompt('Do something', 'print(1)', 'python')
    assert 'Task:\nDo something' in prompt
    assert '```python\nprint(1)\n```' in prompt
