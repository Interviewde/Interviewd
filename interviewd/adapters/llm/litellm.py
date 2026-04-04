from typing import AsyncIterator

import litellm

from interviewd.adapters.llm.base import LLMAdapter
from interviewd.config import LLMConfig

# Suppress LiteLLM's verbose logging — it prints provider banners by default.
litellm.suppress_debug_info = True


class LiteLLMAdapter(LLMAdapter, provider="litellm"):
    """LLM adapter backed by LiteLLM — covers 100+ providers via model string.

    No code changes needed to switch providers; update config/default.yaml:

        llm:
          provider: litellm
          model: gemini/gemini-1.5-flash    # Google Gemini
          model: groq/llama3-70b-8192       # Groq
          model: openai/gpt-4o              # OpenAI
          model: ollama/llama3              # Local via Ollama

    Full model list: https://docs.litellm.ai/docs/providers
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)

    async def complete(self, messages: list[dict], stream: bool = True) -> str:
        """Return the full model response as a string.

        When stream=True, internally streams for lower time-to-first-token but
        collects all chunks before returning.
        """
        if stream:
            chunks: list[str] = []
            async for token in self.stream(messages):
                chunks.append(token)
            return "".join(chunks)

        response = await litellm.acompletion(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=False,
        )
        return response.choices[0].message.content or ""

    async def stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield response tokens as they arrive.

        Designed for low-latency piping to TTS — callers can start speaking
        the first sentence while the rest of the response is still generating.
        """
        response = await litellm.acompletion(
            model=self.config.model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=True,
        )
        async for chunk in response:
            token = chunk.choices[0].delta.content
            if token:
                yield token
