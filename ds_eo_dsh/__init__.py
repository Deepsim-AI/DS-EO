# DS-EO DSH Edition — Python Package
# DeepSeek Harness (DSH) runtime adapter for the Deepsim Engineering Organization

from pathlib import Path

__version__ = "0.1.0-pre"

# Version helper: read from VERSION file if present
try:
    _ver_file = Path(__file__).resolve().parent / "VERSION"
    if _ver_file.exists():
        __version__ = _ver_file.read_text().strip()
except Exception:
    pass

# Runtime API — the single entry point for adapter instantiation
from ds_eo_dsh.adapter.runtime_api import (
    RuntimeAPI,
    RuntimeModel,
    RuntimeSession,
    ActionResult,
)

# Factory — create runtime instances
from ds_eo_dsh.adapter.runtime_api import RuntimeAdapterFactory

# Public exports
__all__ = [
    "__version__",
    "RuntimeAPI",
    "RuntimeModel",
    "RuntimeSession",
    "ActionResult",
    "RuntimeAdapterFactory",
]
