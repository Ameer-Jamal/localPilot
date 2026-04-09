import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from transcript_render import (
    block_has_role,
    render_code_context_block,
    render_message_block,
    render_thinking_block,
    role_label,
)


def test_role_label_maps_known_roles():
    assert role_label("user") == "you"
    assert role_label("assistant") == "assistant"
    assert role_label("system") == "system"


def test_render_message_block_wraps_rendered_html():
    html = render_message_block("user", "<p>Hello</p>")
    assert 'class="message message-user"' in html
    assert 'data-role="user"' in html
    assert '<div class="role">you</div>' in html
    assert '<div class="message-body"><p>Hello</p></div>' in html


def test_render_code_context_block_wraps_details_and_code():
    html = render_code_context_block("print('x')", "python")
    assert 'class="message message-system"' in html
    assert "Pinned code context (python)" in html
    assert "print(&#x27;x&#x27;)" in html


def test_block_has_role_matches_message_role_only():
    assistant = render_message_block("assistant", "<p>Hello</p>")
    system = render_code_context_block("print('x')", "python")
    assert block_has_role(assistant, "assistant")
    assert not block_has_role(system, "assistant")


def test_render_thinking_block_marks_assistant_as_thinking():
    html = render_thinking_block()
    assert 'data-role="assistant"' in html
    assert 'data-state="thinking"' in html
    assert 'class="thinking-indicator"' in html
    assert 'Thinking' in html
