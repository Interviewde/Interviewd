import asyncio
import io
import wave

from interviewd.adapters.tts.base import TTSAdapter
from interviewd.config import TTSConfig


class PiperTTSAdapter(TTSAdapter, provider="piper"):
    """TTS adapter using Piper TTS — fully offline, no API key required.

    Requires downloading a voice model (.onnx + .onnx.json pair).

    Install the extra:
        uv pip install interviewd[piper]

    Download a voice model:
        https://github.com/rhasspy/piper/releases

    Config options (config/default.yaml):
        tts:
          provider: piper
          voice: /path/to/en_US-lessac-medium.onnx

    Both the .onnx model and its .onnx.json config file must be in the
    same directory. The voice field should point to the .onnx file.

    Recommended models for low-latency use:
        en_US-lessac-medium   ~63 MB   good balance of quality and speed
        en_US-ryan-low        ~28 MB   fastest, lower quality
    """

    def __init__(self, config: TTSConfig):
        super().__init__(config)
        self._voice = None  # lazy-loaded on first use to avoid startup delay

    @property
    def voice(self):
        from piper import PiperVoice

        if self._voice is None:
            self._voice = PiperVoice.load(self.config.voice)
        return self._voice

    async def synthesize(self, text: str) -> bytes:
        """Convert text to WAV audio bytes using Piper.

        Piper's API is synchronous, so synthesis runs in a thread executor
        to avoid blocking the async event loop.

        Args:
            text: The text to synthesize.

        Returns:
            Raw WAV audio bytes.
        """

        def _run() -> bytes:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav_file:
                self.voice.synthesize(text, wav_file)
            return buf.getvalue()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _run)

    async def speak(self, text: str) -> None:
        """Synthesize text and play through speakers via sounddevice.

        Buffers the full audio before playback.

        Args:
            text: The text to be spoken aloud.
        """
        import sounddevice as sd
        import soundfile as sf

        audio_bytes = await self.synthesize(text)
        data, samplerate = sf.read(io.BytesIO(audio_bytes))
        sd.play(data, samplerate)
        sd.wait()
