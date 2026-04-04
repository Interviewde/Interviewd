from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interviewd.adapters.tts.registry import get_tts_adapter
from interviewd.config import TTSConfig


def test_edge_tts_adapter_is_registered():
    """Edge TTS adapter should be auto-discovered and available by name."""
    config = TTSConfig(provider="edge_tts")
    adapter = get_tts_adapter(config)
    assert adapter is not None
    assert adapter.config.provider == "edge_tts"


def test_piper_adapter_is_registered():
    """Piper adapter should be auto-discovered and available by name."""
    config = TTSConfig(provider="piper", voice="/path/to/model.onnx")
    adapter = get_tts_adapter(config)
    assert adapter is not None
    assert adapter.config.provider == "piper"


def test_adapter_receives_config():
    """Adapter should store the config passed from the registry."""
    config = TTSConfig(provider="edge_tts", voice="en-GB-SoniaNeural")
    adapter = get_tts_adapter(config)
    assert adapter.config.voice == "en-GB-SoniaNeural"


@pytest.mark.asyncio
async def test_edge_tts_synthesize():
    """Edge TTS adapter should collect audio chunks and return combined bytes."""
    config = TTSConfig(provider="edge_tts")

    async def mock_stream():
        yield {"type": "audio", "data": b"chunk1"}
        yield {"type": "WordBoundary", "data": None}  # non-audio events ignored
        yield {"type": "audio", "data": b"chunk2"}

    mock_communicate = MagicMock()
    mock_communicate.stream = mock_stream

    with patch(
        "interviewd.adapters.tts.edgetts.edge_tts.Communicate",
        return_value=mock_communicate,
    ):
        adapter = get_tts_adapter(config)
        result = await adapter.synthesize("Hello world")

    assert result == b"chunk1chunk2"


@pytest.mark.asyncio
async def test_piper_synthesize():
    """Piper adapter should run synthesis in an executor and return WAV bytes."""
    config = TTSConfig(provider="piper", voice="/path/to/model.onnx")
    fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "

    with patch(
        "interviewd.adapters.tts.piper.asyncio.get_running_loop"
    ) as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value=fake_wav)
        mock_get_loop.return_value = mock_loop

        adapter = get_tts_adapter(config)
        result = await adapter.synthesize("Hello world")

    assert result == fake_wav
