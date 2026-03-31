import importlib
import pkgutil
from pathlib import Path

from interviewd.adapters.llm.base import LLMAdapter


def _autodiscover() -> None:
    """Import all modules in this package so __init_subclass__ fires for each adapter."""
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name not in ("base", "registry"):
            importlib.import_module(f"interviewd.adapters.llm.{module_name}")


def get_llm_adapter(provider: str) -> LLMAdapter:
    _autodiscover()
    if provider not in LLMAdapter._registry:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Available providers: {list(LLMAdapter._registry)}\n"
            f"To use any of 100+ providers without code, set provider to 'litellm'.\n"
            f"See docs/decisions/001-adapter-strategy.md for details."
        )
    return LLMAdapter._registry[provider]()
