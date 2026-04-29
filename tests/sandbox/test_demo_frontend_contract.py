from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_FRONTEND = REPO_ROOT / "demo-frontend"


def test_demo_frontend_has_static_visual_entrypoint() -> None:
    index = (DEMO_FRONTEND / "index.html").read_text(encoding="utf-8")
    styles = (DEMO_FRONTEND / "styles.css").read_text(encoding="utf-8")
    readme = (DEMO_FRONTEND / "README.md").read_text(encoding="utf-8")

    assert "<title>SAEP Demo Frontend</title>" in index
    assert '<link rel="stylesheet" href="styles.css">' in index
    assert 'data-agent-edit-target="headline"' in index
    assert "Sandbox Demo" in index
    assert "--accent-color: #2563eb;" in styles
    assert "Open `index.html` in a browser" in readme


def test_demo_frontend_contains_stable_agent_edit_markers() -> None:
    index = (DEMO_FRONTEND / "index.html").read_text(encoding="utf-8")
    styles = (DEMO_FRONTEND / "styles.css").read_text(encoding="utf-8")

    assert "Sandbox Demo" in index
    assert "Sandbox Agent Demo" not in index
    assert "#2563eb" in styles
    assert "#7c3aed" not in styles
