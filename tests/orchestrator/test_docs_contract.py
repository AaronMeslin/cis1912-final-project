from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_makefile_exposes_orchestrator_commands() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "orchestrator-dev" in makefile
    assert "orchestrator-test" in makefile
    assert "orchestrator-smoke" in makefile
    assert "saep-orchestrator" in makefile
    assert "/sandboxes" in makefile


def test_docs_describe_local_orchestrator_demo() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    control_plane = (REPO_ROOT / "control-plane" / "README.md").read_text(encoding="utf-8")

    assert "make orchestrator-dev" in readme
    assert "make orchestrator-smoke" in readme
    assert "Docker-backed sandbox lifecycle" in readme
    assert "SANDBOX_ORCHESTRATOR_URL" in control_plane
    assert "POST /sandboxes" in control_plane
