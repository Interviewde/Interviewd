import io

import edge_tts
import sounddevice as sd
import soundfile as sf

from interviewd.adapters.tts.base import TTSAdapter
from interviewd.config import TTSConfig


class EdgeTTSAdapter(TTSAdapter, provider="edge_tts"):
    """TTS adapter using Microsoft Edge TTS (edge-tts library).

    No API key required — uses Microsoft's neural TTS service over the internet.

    Config options (config/default.yaml):
        tts:
          provider: edge_tts
          voice: en-US-AriaNeural    # any voice from the edge-tts list

    Browse all available voices:
        edge-tts --list-voices

    Note: speak() requires soundfile >= 0.12 with libsndfile MP3 support,
    which is bundled automatically on Windows via the PyPI wheel.
    """

    def __init__(self, config: TTSConfig):
        super().__init__(config)

    async def synthesize(self, text: str) -> bytes:
        """Convert text to MP3 audio bytes using Edge TTS.

        Args:
            text: The text to synthesize.

        Returns:
            Raw MP3 audio bytes.
        """
        communicate = edge_tts.Communicate(text, self.config.voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    async def speak(self, text: str) -> None:
        """Synthesize text and play through speakers via sounddevice.

        Buffers the full audio before playback.

        Args:
            text: The text to be spoken aloud.
        """
        audio_bytes = await self.synthesize(text)
        data, samplerate = sf.read(io.BytesIO(audio_bytes))
        sd.play(data, samplerate)
        sd.wait()
