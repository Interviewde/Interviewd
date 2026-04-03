from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interviewd.adapters.stt.registry import get_stt_adapter
from interviewd.config import STTConfig


def test_groq_adapter_is_registered():
    """Groq adapter should be auto-discovered and available by name."""
    config = STTConfig(provider="groq")
    adapter = get_stt_adapter(config)
    assert adapter is not None
    assert adapter.config.provider == "groq"


def test_whisper_local_adapter_is_registered():
    """Whisper local adapter should be auto-discovered and available by name."""
    config = STTConfig(provider="whisper_local")
    adapter = get_stt_adapter(config)
    assert adapter is not None
    assert adapter.config.provider == "whisper_local"


def test_adapter_receives_config():
    """Adapter should store the config passed from the registry."""
    config = STTConfig(provider="groq", model="whisper-large-v3", language="fr")
    adapter = get_stt_adapter(config)
    assert adapter.config.model == "whisper-large-v3"
    assert adapter.config.language == "fr"


@pytest.mark.asyncio
async def test_groq_transcribe():
    """Groq adapter should call the Groq API and return the transcript text."""
    config = STTConfig(provider="groq")

    mock_transcription = MagicMock()
    mock_transcription.text = "Tell me about yourself."

    with patch("interviewd.adapters.stt.groq.AsyncGroq") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_transcription)

        adapter = get_stt_adapter(config)
        result = await adapter.transcribe(b"fake-audio-bytes")

    assert result == "Tell me about yourself."


@pytest.mark.asyncio
async def test_whisper_local_transcribe():
    """Whisper local adapter should call whisper.transcribe and return stripped text."""
    config = STTConfig(provider="whisper_local", model="base")

    with patch("interviewd.adapters.stt.whisper_local.asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(
            return_value={"text": "  Hello world.  "}
        )
        with patch("builtins.open", MagicMock()):
            with patch("interviewd.adapters.stt.whisper_local.tempfile.NamedTemporaryFile") as mock_tmp:
                mock_tmp.return_value.__enter__ = MagicMock(return_value=MagicMock(name="f"))
                mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
                with patch("interviewd.adapters.stt.whisper_local.Path.unlink"):
                    adapter = get_stt_adapter(config)
                    result = await adapter.transcribe(b"fake-audio-bytes")

    assert result == "Hello world."
