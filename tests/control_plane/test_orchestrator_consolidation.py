from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_project_uses_only_fastapi_orchestrator_entrypoint() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert not (REPO_ROOT / "orchestrator").exists()
    assert not (REPO_ROOT / "tests" / "orchestrator").exists()
    assert "saep-orchestrator" not in pyproject
    assert 'packages = ["snapshot"]' in pyproject
    assert "orchestrator-dev" not in makefile
    assert "orchestrator-smoke" not in makefile
    assert "two local orchestrator entrypoints" not in readme
    assert "make orchestrator-up" in readme
