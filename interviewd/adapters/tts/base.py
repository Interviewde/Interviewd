from abc import ABC, abstractmethod


class TTSAdapter(ABC):
    """Base class for all Text-to-Speech adapters.

    # For end users
    Set tts.provider in config/default.yaml to use a built-in provider.
    No code changes needed. Built-in providers: edge_tts, piper.

    # For contributors adding a new TTS provider
    Create a new file in interviewd/adapters/tts/ and declare your class
    with a provider keyword argument. Registration and discovery are automatic:

        class MyAdapter(TTSAdapter, provider="my_provider"):
            async def speak(self, text: str) -> None:
                ...

    See docs/decisions/001-adapter-strategy.md for the reasoning behind
    this design.
    """

    _registry: dict[str, type["TTSAdapter"]] = {}

    def __init_subclass__(cls, provider: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if provider is not None:
            TTSAdapter._registry[provider] = cls

    @abstractmethod
    async def speak(self, text: str) -> None:
        """Convert text to speech and play it through the speakers.

        Args:
            text: The text to be spoken aloud.
        """

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Convert text to raw audio bytes without playing it.

        Useful for testing or saving audio to disk.

        Args:
            text: The text to synthesize.

        Returns:
            Raw audio bytes.
        """
