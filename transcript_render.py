from __future__ import annotations

from html import escape


def role_label(role: str) -> str:
    return {"system": "system", "user": "you", "assistant": "assistant"}.get(role, role)


def render_message_block(role: str, rendered_html: str) -> str:
    label = role_label(role)
    return (
        f'<section class="message message-{escape(role)}" data-role="{escape(role)}">'
        f'<div class="role">{escape(label)}</div>'
        f'<div class="message-body">{rendered_html}</div>'
        f"</section>"
    )


def render_thinking_block() -> str:
    return (
        '<section class="message message-assistant" data-role="assistant" data-state="thinking">'
        '<div class="role">assistant</div>'
        '<div class="message-body">'
        '<div class="thinking-indicator" aria-label="Assistant is thinking">'
        '<span class="thinking-label">Thinking</span>'
        '<span class="thinking-dots" aria-hidden="true">'
        '<span></span><span></span><span></span>'
        '</span>'
        '</div>'
        '</div>'
        '</section>'
    )


def block_has_role(block_html: str, role: str) -> bool:
    return f'data-role="{escape(role)}"' in (block_html or "")


def render_code_context_block(code: str, lang: str) -> str:
    return (
        '<section class="message message-system" data-role="system">'
        '<div class="role">system</div>'
        '<div class="message-body">'
        f'<details open>'
        f'<summary style="cursor:pointer">Pinned code context ({escape(lang)})</summary>'
        f'<pre><code class="language-{escape(lang)}">{escape(code)}</code></pre>'
        f"</details><hr/>"
        "</div>"
        "</section>"
    )
