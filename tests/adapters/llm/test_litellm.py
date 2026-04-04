from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interviewd.adapters.llm.registry import get_llm_adapter
from interviewd.config import LLMConfig


def _make_chunk(content: str | None):
    chunk = MagicMock()
    chunk.choices[0].delta.content = content
    return chunk


class _AsyncIter:
    """Wraps a list of chunks as an async iterable — mimics LiteLLM's stream response."""

    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for c in self._chunks:
            yield c


def test_litellm_adapter_is_registered():
    config = LLMConfig(provider="litellm")
    adapter = get_llm_adapter(config)
    assert adapter is not None
    assert adapter.config.provider == "litellm"


def test_adapter_receives_config():
    config = LLMConfig(provider="litellm", model="openai/gpt-4o", temperature=0.3, max_tokens=512)
    adapter = get_llm_adapter(config)
    assert adapter.config.model == "openai/gpt-4o"
    assert adapter.config.temperature == 0.3
    assert adapter.config.max_tokens == 512


@pytest.mark.asyncio
async def test_complete_no_stream_returns_text():
    config = LLMConfig(provider="litellm")
    adapter = get_llm_adapter(config)

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Great answer."

    with patch("interviewd.adapters.llm.litellm.litellm.acompletion", new=AsyncMock(return_value=mock_response)):
        result = await adapter.complete([{"role": "user", "content": "Hi"}], stream=False)

    assert result == "Great answer."


@pytest.mark.asyncio
async def test_complete_stream_true_collects_tokens():
    config = LLMConfig(provider="litellm")
    adapter = get_llm_adapter(config)

    chunks = [_make_chunk("Hello"), _make_chunk(" world"), _make_chunk(None), _make_chunk("!")]

    with patch(
        "interviewd.adapters.llm.litellm.litellm.acompletion",
        new=AsyncMock(return_value=_AsyncIter(chunks)),
    ):
        result = await adapter.complete([{"role": "user", "content": "Hi"}], stream=True)

    assert result == "Hello world!"


@pytest.mark.asyncio
async def test_stream_yields_tokens():
    config = LLMConfig(provider="litellm")
    adapter = get_llm_adapter(config)

    chunks = [_make_chunk("One"), _make_chunk(None), _make_chunk("Two")]

    with patch(
        "interviewd.adapters.llm.litellm.litellm.acompletion",
        new=AsyncMock(return_value=_AsyncIter(chunks)),
    ):
        tokens = [t async for t in adapter.stream([{"role": "user", "content": "Hi"}])]

    assert tokens == ["One", "Two"]


@pytest.mark.asyncio
async def test_complete_no_stream_empty_content():
    """Handles None content gracefully — returns empty string."""
    config = LLMConfig(provider="litellm")
    adapter = get_llm_adapter(config)

    mock_response = MagicMock()
    mock_response.choices[0].message.content = None

    with patch("interviewd.adapters.llm.litellm.litellm.acompletion", new=AsyncMock(return_value=mock_response)):
        result = await adapter.complete([{"role": "user", "content": "Hi"}], stream=False)

    assert result == ""


def test_unknown_provider_raises():
    config = LLMConfig(provider="does_not_exist")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_adapter(config)
