import wave
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from interviewd.engine.voice_loop import VoiceLoop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapters(vad_side_effect):
    """Return (vad, stt, tts) mocks wired up for a listen() run.

    vad_side_effect: iterable of booleans returned by vad.is_speech in order.
    """
    mock_vad = MagicMock()
    mock_vad.config.sample_rate = 16000
    mock_vad.is_speech = AsyncMock(side_effect=vad_side_effect)

    mock_stt = MagicMock()
    mock_stt.transcribe = AsyncMock(return_value="Hello world.")

    mock_tts = MagicMock()
    mock_tts.speak = AsyncMock()

    return mock_vad, mock_stt, mock_tts


def _make_stream_mock():
    """Return a mock sounddevice InputStream whose .read() returns fake PCM."""
    fake_chunk = MagicMock()
    fake_chunk.tobytes.return_value = b"\x00\x00" * 1536  # 1536 silent int16 samples

    mock_stream = MagicMock()
    mock_stream.read.return_value = (fake_chunk, False)
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    return mock_stream


# ---------------------------------------------------------------------------
# Tests: listen()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_listen_returns_transcript():
    """listen() should return the transcript from STT after detecting speech."""
    # VAD sequence: silence → speech → speech → silence → silence (end-of-utterance)
    # With silence_timeout_ms=200 → silence_chunks = 200 // 96 = 2
    vad_seq = [False, True, True, False, False]
    mock_vad, mock_stt, mock_tts = _make_adapters(vad_seq)
    mock_stream = _make_stream_mock()

    voice_loop = VoiceLoop(
        mock_vad, mock_stt, mock_tts, silence_timeout_ms=200, pre_speech_pad_ms=96
    )

    with patch("interviewd.engine.voice_loop.sd.InputStream", return_value=mock_stream):
        result = await voice_loop.listen()

    assert result == "Hello world."
    mock_stt.transcribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_listen_passes_wav_to_stt():
    """listen() should encode accumulated PCM as WAV before calling stt.transcribe."""
    vad_seq = [False, True, False, False]
    mock_vad, mock_stt, mock_tts = _make_adapters(vad_seq)
    mock_stream = _make_stream_mock()

    voice_loop = VoiceLoop(
        mock_vad, mock_stt, mock_tts, silence_timeout_ms=200, pre_speech_pad_ms=96
    )

    with patch("interviewd.engine.voice_loop.sd.InputStream", return_value=mock_stream):
        await voice_loop.listen()

    wav_bytes = mock_stt.transcribe.call_args[0][0]
    assert wav_bytes[:4] == b"RIFF", "STT should receive WAV-encoded bytes"


@pytest.mark.asyncio
async def test_listen_includes_pre_speech_pad():
    """listen() pre-pad frames should appear in the WAV sent to STT.

    With pre_speech_pad_ms=96 (one chunk) and silence_timeout_ms=200:
    - chunk 0: silence → goes into pre_pad
    - chunk 1: speech  → pre_pad flushed + speech frame added
    - chunk 2: silence, chunk 3: silence → end-of-utterance
    The WAV should contain 3 chunks of PCM (pre_pad + chunk1 + chunk2 + chunk3).
    """
    # chunk 0 silent, chunk 1 speech, chunk 2 silence, chunk 3 silence
    vad_seq = [False, True, False, False]
    mock_vad, mock_stt, mock_tts = _make_adapters(vad_seq)
    mock_stream = _make_stream_mock()

    voice_loop = VoiceLoop(
        mock_vad, mock_stt, mock_tts, silence_timeout_ms=200, pre_speech_pad_ms=96
    )

    with patch("interviewd.engine.voice_loop.sd.InputStream", return_value=mock_stream):
        await voice_loop.listen()

    wav_bytes = mock_stt.transcribe.call_args[0][0]
    # Read back the WAV to count samples
    with wave.open(io.BytesIO(wav_bytes)) as wf:
        n_frames = wf.getnframes()
    # 4 chunks × 1536 samples = 6144 total (pre_pad chunk0 + chunk1 + chunk2 + chunk3)
    assert n_frames == 4 * 1536


@pytest.mark.asyncio
async def test_listen_raises_when_no_speech_detected():
    """listen() should raise RuntimeError if max_duration_s passes with no speech."""
    # All chunks return silence; with max_duration_s=0.1 only ~1 chunk is allowed
    # We use a very short max and all-silence VAD to trigger the error quickly.
    vad_seq = [False] * 5
    mock_vad, mock_stt, mock_tts = _make_adapters(vad_seq)
    mock_stream = _make_stream_mock()

    # max_duration_s=0.1 → max_chunks = int(0.1 * 1000 / 96) = 1
    voice_loop = VoiceLoop(mock_vad, mock_stt, mock_tts, max_duration_s=0)

    with patch("interviewd.engine.voice_loop.sd.InputStream", return_value=mock_stream):
        with pytest.raises(RuntimeError, match="No speech detected"):
            await voice_loop.listen()


# ---------------------------------------------------------------------------
# Tests: speak()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_speak_delegates_to_tts():
    """speak() should call tts.speak with the given text."""
    mock_vad, mock_stt, mock_tts = _make_adapters([])

    voice_loop = VoiceLoop(mock_vad, mock_stt, mock_tts)
    await voice_loop.speak("Good morning.")

    mock_tts.speak.assert_awaited_once_with("Good morning.")


# ---------------------------------------------------------------------------
# Tests: _encode_wav()
# ---------------------------------------------------------------------------

def test_encode_wav_produces_valid_wav():
    """_encode_wav should produce valid mono 16-bit WAV at the VAD sample rate."""
    mock_vad = MagicMock()
    mock_vad.config.sample_rate = 16000
    voice_loop = VoiceLoop(mock_vad, MagicMock(), MagicMock())

    # Two frames of 512 samples each (512 int16 = 1024 bytes per frame)
    frame = b"\x00\x00" * 512
    wav_bytes = voice_loop._encode_wav([frame, frame])

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 1024  # 2 × 512


def test_encode_wav_empty_frames():
    """_encode_wav with no frames should produce a valid WAV with 0 samples."""
    mock_vad = MagicMock()
    mock_vad.config.sample_rate = 16000
    voice_loop = VoiceLoop(mock_vad, MagicMock(), MagicMock())

    wav_bytes = voice_loop._encode_wav([])

    with wave.open(io.BytesIO(wav_bytes)) as wf:
        assert wf.getnframes() == 0
