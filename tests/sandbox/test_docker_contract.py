from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_dockerfile_installs_safe_run_and_uses_non_root_agent() -> None:
    dockerfile = read_repo_file("sandbox/Dockerfile")

    assert "COPY pyproject.toml /tmp/saep/pyproject.toml" in dockerfile
    assert "COPY snapshot /tmp/saep/snapshot" in dockerfile
    assert "COPY orchestrator /tmp/saep/orchestrator" not in dockerfile
    assert "python3 -m pip install --break-system-packages /tmp/saep" in dockerfile
    assert "useradd --system --gid agent --home-dir /workspace --shell /bin/bash agent" in dockerfile
    assert "chown -R agent:agent /workspace" in dockerfile
    assert "USER agent" in dockerfile


def test_dockerfile_wires_healthcheck_script() -> None:
    dockerfile = read_repo_file("sandbox/Dockerfile")
    healthcheck = read_repo_file("sandbox/healthcheck.sh")

    assert "COPY sandbox/healthcheck.sh /usr/local/bin/saep-healthcheck" in dockerfile
    assert 'CMD ["/usr/local/bin/saep-healthcheck"]' in dockerfile
    assert "command -v" in healthcheck
    assert "safe-run" in healthcheck
    assert "chromium" in healthcheck
    assert "test -w /workspace" in healthcheck


def test_makefile_builds_from_repo_root_and_smoke_tests_safe_run() -> None:
    makefile = read_repo_file("Makefile")

    assert ".PHONY:" in makefile
    assert "sandbox-smoke" in makefile
    assert "docker build -t $(IMAGE_NAME):$(IMAGE_TAG) -f sandbox/Dockerfile ." in makefile
    assert "sandbox-smoke:" in makefile
    assert "safe-run run python3 -c" in makefile
    assert "safe-run diff" in makefile
    assert "safe-run undo" in makefile


def test_ci_builds_root_context_and_runs_docker_smoke() -> None:
    workflow = read_repo_file(".github/workflows/ci.yml")

    assert "context: ." in workflow
    assert "tags: saep-sandbox:ci" in workflow
    assert "Docker sandbox smoke test" in workflow
    assert "make sandbox-smoke IMAGE_TAG=ci" in workflow
