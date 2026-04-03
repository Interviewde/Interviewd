import asyncio
import io
import tempfile
from pathlib import Path

from interviewd.adapters.stt.base import STTAdapter
from interviewd.config import STTConfig


class WhisperLocalSTTAdapter(STTAdapter, provider="whisper_local"):
    """STT adapter using OpenAI Whisper running locally on CPU.

    No API key required — runs entirely offline.
    Requires the openai-whisper package (already in pyproject.toml).

    Model sizes and approximate disk usage:
        tiny    ~75 MB   fastest, least accurate
        base    ~150 MB  good balance for most laptops   ← recommended
        small   ~500 MB
        medium  ~1.5 GB
        large   ~3 GB

    Config options (config/default.yaml):
        stt:
          provider: whisper_local
          model: base     # use tiny if CPU is slow
          language: en
    """

    def __init__(self, config: STTConfig):
        super().__init__(config)
        self._model = None  # lazy-loaded on first transcription to avoid slow startup

    @property
    def model(self):
        # Import here so whisper is only loaded when this adapter is actually used
        import whisper
        if self._model is None:
            self._model = whisper.load_model(self.config.model or "base")
        return self._model

    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio bytes using local Whisper model.

        Whisper's Python API is synchronous, so we run it in a thread
        to avoid blocking the async event loop.

        Args:
            audio: Raw audio bytes in WAV format.

        Returns:
            Transcribed text string.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio)
            tmp_path = f.name

        try:
            # run_in_executor moves the blocking whisper call off the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.model.transcribe(tmp_path, language=self.config.language),
            )
            return result["text"].strip()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
