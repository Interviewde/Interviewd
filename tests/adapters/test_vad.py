from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interviewd.adapters.vad.registry import get_vad_adapter
from interviewd.config import VADConfig


def test_silero_adapter_is_registered():
    """Silero adapter should be auto-discovered and available by name."""
    config = VADConfig(provider="silero")
    adapter = get_vad_adapter(config)
    assert adapter is not None
    assert adapter.config.provider == "silero"


def test_adapter_receives_config():
    """Adapter should store the config values passed from the registry."""
    config = VADConfig(provider="silero", threshold=0.7, sample_rate=16000)
    adapter = get_vad_adapter(config)
    assert adapter.config.threshold == 0.7
    assert adapter.config.sample_rate == 16000


@pytest.mark.asyncio
async def test_silero_is_speech_true_above_threshold():
    """is_speech() should return True when executor returns True."""
    config = VADConfig(provider="silero", threshold=0.5)

    with patch("interviewd.adapters.vad.silero.asyncio.get_running_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value=True)
        mock_get_loop.return_value = mock_loop

        adapter = get_vad_adapter(config)
        result = await adapter.is_speech(b"\x00" * 1024)

    assert result is True


@pytest.mark.asyncio
async def test_silero_is_speech_false_below_threshold():
    """is_speech() should return False when executor returns False."""
    config = VADConfig(provider="silero", threshold=0.5)

    with patch("interviewd.adapters.vad.silero.asyncio.get_running_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.run_in_executor = AsyncMock(return_value=False)
        mock_get_loop.return_value = mock_loop

        adapter = get_vad_adapter(config)
        result = await adapter.is_speech(b"\x00" * 1024)

    assert result is False


def test_unknown_provider_raises():
    """Registry should raise ValueError for an unrecognised provider name."""
    # VADConfig uses Literal so we bypass validation to test the registry guard
    config = VADConfig.model_construct(provider="nonexistent")
    with pytest.raises(ValueError, match="Unknown VAD provider"):
        get_vad_adapter(config)
