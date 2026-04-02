from abc import ABC, abstractmethod

from interviewd.config import STTConfig


class STTAdapter(ABC):
    """Base class for all Speech-to-Text adapters.

    # For end users
    Set stt.provider in config/default.yaml to use a built-in provider.
    No code changes needed. Built-in providers: groq, whisper_local.

    # For contributors adding a new STT provider
    Create a new file in interviewd/adapters/stt/ and declare your class
    with a provider keyword argument. Registration and discovery are automatic:

        class MyAdapter(STTAdapter, provider="my_provider"):
            def __init__(self, config: STTConfig):
                super().__init__(config)
                # initialise your client here

            async def transcribe(self, audio: bytes) -> str:
                ...

    See docs/decisions/001-adapter-strategy.md for the reasoning behind
    this design.
    """

    _registry: dict[str, type["STTAdapter"]] = {}

    def __init__(self, config: STTConfig):
        self.config = config

    def __init_subclass__(cls, provider: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if provider is not None:
            STTAdapter._registry[provider] = cls

    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """Convert raw audio bytes to a text transcript.

        Args:
            audio: Raw PCM audio bytes in WAV format captured from the microphone.

        Returns:
            The transcribed text string.
        """
