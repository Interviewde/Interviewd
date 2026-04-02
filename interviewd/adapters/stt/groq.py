import io

from groq import AsyncGroq

from interviewd.adapters.stt.base import STTAdapter
from interviewd.config import STTConfig


class GroqSTTAdapter(STTAdapter, provider="groq"):
    """STT adapter using Groq's Whisper API.

    Requires GROQ_API_KEY environment variable.
    Get a free key at https://console.groq.com

    Config options (config/default.yaml):
        stt:
          provider: groq
          model: whisper-large-v3-turbo   # or whisper-large-v3
          language: en                    # ISO 639-1 language code
    """

    def __init__(self, config: STTConfig):
        super().__init__(config)
        # AsyncGroq reads GROQ_API_KEY from the environment automatically
        self.client = AsyncGroq()

    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio bytes using Groq Whisper.

        Args:
            audio: Raw audio bytes in WAV format.

        Returns:
            Transcribed text string.
        """
        # Groq SDK requires a file-like object with a .name attribute
        # so it can infer the audio format from the extension
        audio_file = io.BytesIO(audio)
        audio_file.name = "audio.wav"

        transcription = await self.client.audio.transcriptions.create(
            file=audio_file,
            model=self.config.model,
            language=self.config.language,
        )
        return transcription.text
