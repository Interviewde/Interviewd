import importlib
import pkgutil
from pathlib import Path

from interviewd.adapters.vad.base import VADAdapter
from interviewd.config import VADConfig


def _autodiscover() -> None:
    """Import all modules in this package so __init_subclass__ fires for each adapter."""
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name not in ("base", "registry"):
            importlib.import_module(f"interviewd.adapters.vad.{module_name}")


def get_vad_adapter(config: VADConfig) -> VADAdapter:
    _autodiscover()
    if config.provider not in VADAdapter._registry:
        raise ValueError(
            f"Unknown VAD provider '{config.provider}'. "
            f"Available providers: {list(VADAdapter._registry)}\n"
            f"See docs/decisions/001-adapter-strategy.md to add a new provider."
        )
    return VADAdapter._registry[config.provider](config)
