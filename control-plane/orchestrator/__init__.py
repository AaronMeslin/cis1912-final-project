"""Local Docker orchestrator package for the SAEP control plane."""

from pathlib import Path

_top_level_orchestrator = Path(__file__).resolve().parents[2] / "orchestrator"
if _top_level_orchestrator.is_dir():
    __path__.append(_top_level_orchestrator.as_posix())
