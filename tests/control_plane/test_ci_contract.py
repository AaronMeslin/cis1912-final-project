from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
E2E_TEST = REPO_ROOT / "tests" / "e2e" / "test_local_worker_flow.py"
MAKEFILE = REPO_ROOT / "Makefile"


def test_ci_runs_full_python_suite_with_orchestrator_dependencies() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert 'python3 -m pip install -e ".[dev,orchestrator]"' in workflow
    assert "make test PYTHON=python3" in workflow
    assert "tests/control_plane" in workflow


def test_ci_runs_worker_orchestrator_docker_e2e_smoke() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "worker-orchestrator-e2e" in workflow
    assert "saep-sandbox:ci" in workflow
    assert "make e2e-smoke PYTHON=python3 SAEP_SANDBOX_IMAGE=saep-sandbox:ci" in workflow


def test_e2e_smoke_uses_configurable_sandbox_image() -> None:
    source = E2E_TEST.read_text(encoding="utf-8")
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert 'os.environ.get("SAEP_SANDBOX_IMAGE", "saep-sandbox:local")' in source
    assert "SAEP_SANDBOX_IMAGE ?= saep-sandbox:local" in makefile
    assert "SAEP_SANDBOX_IMAGE=$(SAEP_SANDBOX_IMAGE)" in makefile
