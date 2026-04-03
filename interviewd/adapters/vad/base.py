from abc import ABC, abstractmethod

from interviewd.config import VADConfig


class VADAdapter(ABC):
    """Base class for all Voice Activity Detection adapters.

    # For end users
    Set vad.provider in config/default.yaml to use a built-in provider.
    No code changes needed. Built-in providers: silero.

    # For contributors adding a new VAD provider
    Create a new file in interviewd/adapters/vad/ and declare your class
    with a provider keyword argument. Registration and discovery are automatic:

        class MyAdapter(VADAdapter, provider="my_provider"):
            def __init__(self, config: VADConfig):
                super().__init__(config)

            async def is_speech(self, audio: bytes) -> bool:
                ...

    See docs/decisions/001-adapter-strategy.md for the reasoning behind
    this design.
    """

    _registry: dict[str, type["VADAdapter"]] = {}

    def __init__(self, config: VADConfig):
        self.config = config

    def __init_subclass__(cls, provider: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if provider is not None:
            VADAdapter._registry[provider] = cls

    @abstractmethod
    async def is_speech(self, audio: bytes) -> bool:
        """Determine whether the given audio chunk contains speech.

        Args:
            audio: Raw 16-bit PCM audio bytes, mono, at the configured sample rate.

        Returns:
            True if the chunk is classified as speech, False for silence/noise.
        """
