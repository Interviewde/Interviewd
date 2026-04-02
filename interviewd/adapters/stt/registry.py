import importlib
import pkgutil
from pathlib import Path

from interviewd.adapters.stt.base import STTAdapter


def _autodiscover() -> None:
    """Import all modules in this package so __init_subclass__ fires for each adapter."""
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name not in ("base", "registry"):
            importlib.import_module(f"interviewd.adapters.stt.{module_name}")


def get_stt_adapter(provider: str) -> STTAdapter:
    _autodiscover()
    if provider not in STTAdapter._registry:
        raise ValueError(
            f"Unknown STT provider '{provider}'. "
            f"Available providers: {list(STTAdapter._registry)}\n"
            f"See docs/decisions/001-adapter-strategy.md to add a new provider."
        )
    return STTAdapter._registry[provider]()
