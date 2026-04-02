import importlib
import pkgutil
from pathlib import Path

from interviewd.adapters.tts.base import TTSAdapter
from interviewd.config import TTSConfig


def _autodiscover() -> None:
    """Import all modules in this package so __init_subclass__ fires for each adapter."""
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name not in ("base", "registry"):
            importlib.import_module(f"interviewd.adapters.tts.{module_name}")


def get_tts_adapter(config: TTSConfig) -> TTSAdapter:
    _autodiscover()
    if config.provider not in TTSAdapter._registry:
        raise ValueError(
            f"Unknown TTS provider '{config.provider}'. "
            f"Available providers: {list(TTSAdapter._registry)}\n"
            f"See docs/decisions/001-adapter-strategy.md to add a new provider."
        )
    return TTSAdapter._registry[config.provider](config)
