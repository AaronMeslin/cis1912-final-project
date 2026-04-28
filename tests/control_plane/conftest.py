from __future__ import annotations

import sys
from pathlib import Path


CONTROL_PLANE_ROOT = Path(__file__).resolve().parents[2] / "control-plane"
# The Python orchestrator lives under `control-plane/`, whose hyphenated name
# is not directly importable as a package. Add that directory to sys.path so
# tests can import `orchestrator.*` like uvicorn does when run from there.
sys.path.insert(0, CONTROL_PLANE_ROOT.as_posix())
