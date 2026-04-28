"""Local sandbox orchestrator."""

from pathlib import Path

_control_plane_orchestrator = Path(__file__).resolve().parents[1] / "control-plane" / "orchestrator"
if _control_plane_orchestrator.is_dir():
    __path__.append(_control_plane_orchestrator.as_posix())
