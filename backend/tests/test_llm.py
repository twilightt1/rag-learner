from __future__ import annotations

import pytest
from unittest.mock import Mock

from backend.llm.openrouter import complete, stream_complete


@pytest.fixture(autouse=True)
def mock_httpx_client(mocker):
    """Replace httpx.AsyncClient with a mock."""
    return mocker.patch('backend.llm.openrouter.httpx.AsyncClient')


async def test_complete_returns_content(mock_httpx_client):
    """complete() returns the LLM response string."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "The answer is 42."}}]
    }
    mock_response.raise_for_status = Mock()
    mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_response

    result = await complete([{"role": "user", "content": "What is the meaning of life?"}])

    assert result == "The answer is 42."


async def test_complete_raises_on_http_error(mock_httpx_client):
    """complete() raises when response raises."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
    mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_response

    with pytest.raises(Exception, match="401"):
        await complete([{"role": "user", "content": "test"}])


async def test_complete_uses_correct_payload(mock_httpx_client):
    """complete() sends correct JSON payload to OpenRouter."""
    mock_response = Mock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_response.raise_for_status = Mock()
    mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_response

    messages = [{"role": "user", "content": "Hello"}]
    await complete(messages, model="custom-model", max_tokens=512, temperature=0.5)

    call_args = mock_httpx_client.return_value.__aenter__.return_value.post.call_args
    payload = call_args[1]["json"]
    assert payload["model"] == "custom-model"
    assert payload["messages"] == messages
    assert payload["max_tokens"] == 512
    assert payload["temperature"] == 0.5
    assert payload["stream"] is False


async def test_complete_includes_api_key(mock_httpx_client, mocker):
    """complete() includes Authorization header if API key set."""
    from backend.config import get_settings
    mocker.patch.object(get_settings(), 'openrouter_api_key', 'test-key-123')

    mock_response = Mock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    mock_response.raise_for_status = Mock()
    mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_response

    await complete([{"role": "user", "content": "test"}])

    headers = mock_httpx_client.return_value.__aenter__.return_value.post.call_args[1]["headers"]
    assert "Authorization" in headers
    assert headers["Authorization"] == "Bearer test-key-123"


async def test_stream_complete_yields_tokens(mock_httpx_client):
    """stream_complete() yields tokens from SSE stream."""
    class MockStreamResponse:
        def __init__(self, lines):
            self._lines = lines
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        def raise_for_status(self):
            pass
        async def aiter_lines(self):
            for line in self._lines:
                yield line

    sse_lines = [
        "data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}",
        "data: {\"choices\":[{\"delta\":{\"content\":\" World\"}}]}",
        "data: {\"choices\":[{\"delta\":{\"content\":\"!\"}}]}",
        "data: [DONE]",
    ]

    mock_client = mock_httpx_client.return_value
    mock_client.stream.return_value = MockStreamResponse(sse_lines)

    tokens = []
    async for token in stream_complete([{"role": "user", "content": "hi"}]):
        tokens.append(token)

    assert tokens == ["Hello", " World", "!"]


async def test_stream_complete_skips_empty_and_malformed(mock_httpx_client):
    """stream_complete() skips empty lines and malformed chunks."""
    class MockStreamResponse:
        def __init__(self, lines):
            self._lines = lines
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        async def aiter_lines(self):
            for line in self._lines:
                yield line

    sse_lines = [
        "",  # empty
        "data: {}",  # malformed
        "data: {\"choices\":[{\"delta\":{}}]}",  # no content
        "data: [DONE]",
    ]
    mock_client = mock_httpx_client.return_value
    mock_client.stream.return_value = MockStreamResponse(sse_lines)

    tokens = [t async for t in stream_complete([{"role": "user", "content": "test"}])]
    assert tokens == []


async def test_stream_complete_handles_json_error(mock_httpx_client):
    """stream_complete() continues after JSON decode errors."""
    class MockStreamResponse:
        def __init__(self, lines):
            self._lines = lines
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        async def aiter_lines(self):
            for line in self._lines:
                yield line

    sse_lines = [
        "data: invalid json{{{",
        "data: {\"choices\":[{\"delta\":{\"content\":\"Recovered\"}}]}",
        "data: [DONE]",
    ]
    mock_client = mock_httpx_client.return_value
    mock_client.stream.return_value = MockStreamResponse(sse_lines)

    tokens = [t async for t in stream_complete([{"role": "user", "content": "test"}])]
    assert tokens == ["Recovered"]


async def test_stream_uses_correct_payload(mock_httpx_client):
    """stream_complete() sends stream=True in payload."""
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_httpx_client.return_value.__aenter__.return_value.stream.return_value = mock_response

    await stream_complete([{"role": "user", "content": "test"}])

    call_args = mock_httpx_client.return_value.__aenter__.return_value.stream.call_args
    payload = call_args[1]["json"]
    assert payload["stream"] is True
