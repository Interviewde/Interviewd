from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMAdapter(ABC):
    """Base class for all LLM adapters.

    # For end users
    The default LLM adapter uses LiteLLM, which supports 100+ providers
    via config alone. Set llm.provider to "litellm" and llm.model to any
    LiteLLM-supported model string in config/default.yaml:

        llm:
          provider: litellm
          model: gemini/gemini-1.5-flash   # or groq/llama3, mistral/mistral-large

    No code changes needed for any LiteLLM-supported provider.
    Full model list: https://docs.litellm.ai/docs/providers

    # For contributors adding a provider not supported by LiteLLM
    Create a new file in interviewd/adapters/llm/ and declare your class
    with a provider keyword argument. Registration and discovery are automatic:

        class MyAdapter(LLMAdapter, provider="my_provider"):
            async def complete(self, messages, stream=True) -> str:
                ...

    See docs/decisions/001-adapter-strategy.md for the reasoning behind
    this design.
    """

    _registry: dict[str, type["LLMAdapter"]] = {}

    def __init_subclass__(cls, provider: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if provider is not None:
            LLMAdapter._registry[provider] = cls

    @abstractmethod
    async def complete(self, messages: list[dict], stream: bool = True) -> str:
        """Send messages and return the full response as a string.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            stream:   If True, internally streams but returns the full string.

        Returns:
            The model's response as a plain string.
        """

    @abstractmethod
    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Stream the model response token by token.

        Tokens are piped directly to TTS as they arrive to reduce latency.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.

        Yields:
            Individual string tokens as they are generated.
        """
