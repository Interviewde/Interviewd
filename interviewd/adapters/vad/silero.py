import asyncio

from interviewd.adapters.vad.base import VADAdapter
from interviewd.config import VADConfig


class SileroVADAdapter(VADAdapter, provider="silero"):
    """VAD adapter using Silero VAD — lightweight, offline, runs on CPU.

    Install the extra:
        uv pip install interviewd[silero]

    Config options (config/default.yaml):
        vad:
          provider: silero
          threshold: 0.5      # confidence threshold, 0.0–1.0
          sample_rate: 16000  # must be 8000 or 16000

    The model is loaded from PyPI (silero-vad) and cached on first use.
    Audio must be raw 16-bit PCM, mono, at the configured sample rate.
    """

    def __init__(self, config: VADConfig):
        super().__init__(config)
        self._model = None  # lazy-loaded on first use

    @property
    def model(self):
        from silero_vad import load_silero_vad

        if self._model is None:
            self._model = load_silero_vad()
        return self._model

    async def is_speech(self, audio: bytes) -> bool:
        """Run Silero VAD inference on the given audio chunk.

        Silero's model call is synchronous and CPU-bound, so it runs in a
        thread executor to avoid blocking the async event loop.

        Args:
            audio: Raw 16-bit PCM audio bytes, mono, at config.sample_rate.

        Returns:
            True if confidence >= config.threshold, False otherwise.
        """
        def _run() -> bool:
            import numpy as np
            import torch

            # Silero requires exactly 512 samples at 16kHz (256 at 8kHz).
            # Split the input into fixed windows and return True if any window
            # exceeds the threshold — lets callers pass larger buffers freely.
            window_size = 512 if self.config.sample_rate == 16000 else 256

            audio_np = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
            for i in range(0, len(audio_np) - window_size + 1, window_size):
                window = audio_np[i : i + window_size]
                confidence: float = self.model(
                    torch.from_numpy(window), self.config.sample_rate
                ).item()
                if confidence >= self.config.threshold:
                    return True
            return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run)
