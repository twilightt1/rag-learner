from __future__ import annotations

import pytest

from backend.rag.prompt_builder import build_messages, _format_source_label, SYSTEM_PROMPT


def test_build_messages_includes_system_prompt():
    """build_messages starts with the system prompt."""
    context_chunks = [
        {"text": "Chunk 1", "metadata": {"page_num": "1"}},
    ]
    history = []
    messages = build_messages("query", context_chunks, history)

    assert len(messages) >= 1
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT


def test_build_messages_formats_context_blocks():
    """build_messages formats each context chunk with source label."""
    context_chunks = [
        {"text": "First chunk content", "metadata": {"page_num": "1", "section": "Intro"}},
        {"text": "Second chunk", "metadata": {"page_num": "2"}},
    ]
    messages = build_messages("question?", context_chunks, [])

    # After system, the next message should be the user content containing context
    user_msg = messages[1]["content"]
    assert "Context from your documents:" in user_msg
    assert "First chunk content" in user_msg
    assert "Second chunk" in user_msg
    assert "---" in user_msg  # separator


def test_build_messages_appends_history():
    """build_messages includes prior conversation history."""
    context_chunks = [{"text": "context", "metadata": {}}]
    history = [
        {"role": "user", "content": "Previous question"},
        {"role": "assistant", "content": "Previous answer"},
    ]
    messages = build_messages("new question", context_chunks, history)

    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert "user" in roles
    # History should be inserted before current user message
    # Order: system, history user, history assistant, current user
    # Actually build_messages does: [system] + history + [user_content]
    assert messages[1] == {"role": "user", "content": "Previous question"}
    assert messages[2] == {"role": "assistant", "content": "Previous answer"}


def test_build_messages_empty_context():
    """build_messages handles empty context chunks gracefully."""
    context_chunks = []
    messages = build_messages("query?", context_chunks, [])
    user_msg = messages[1]["content"]  # after system
    assert "Context from your documents:" in user_msg
    # Should not crash, just empty context block


def test_format_source_label_with_section_and_page():
    """_format_source_label includes both section and page when available."""
    meta = {"section": "Methods", "page_num": "5"}
    label = _format_source_label(meta, 1)
    assert "Source 1" in label
    assert "section: Methods" in label
    assert "page 5" in label


def test_format_source_label_with_only_page():
    """_format_source_label includes page if present."""
    meta = {"page_num": "10"}
    label = _format_source_label(meta, 2)
    assert "Source 2" in label
    assert "page 10" in label


def test_format_source_label_plain():
    """_format_source_label returns minimal label when no metadata."""
    meta = {}
    label = _format_source_label(meta, 3)
    assert label == "Source 3"
