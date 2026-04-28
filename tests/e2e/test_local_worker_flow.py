from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from docker.errors import DockerException, ImageNotFound, NotFound

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROL_PLANE_ROOT = REPO_ROOT / "control-plane"
API_KEY = "dev-api-key"
INTERNAL_TOKEN = "dev-internal-token"
ORCHESTRATOR_URL = "http://127.0.0.1:9999"
WORKER_URL = "http://127.0.0.1:8787"

pytestmark = [pytest.mark.e2e, pytest.mark.integration]


def test_worker_orchestrator_docker_safe_run_flow(tmp_path: Path) -> None:
    """Exercise the public Worker API through to Docker and safe-run."""
    docker_client = docker_client_or_skip()
    require_port_free(9999)
    require_port_free(8787)
    env = local_env(tmp_path)
    sandbox: dict | None = None

    try:
        with managed_process(orchestrator_cmd(), CONTROL_PLANE_ROOT, env) as orchestrator:
            wait_for_http(f"{ORCHESTRATOR_URL}/healthz", expected_status=200, process=orchestrator)
            with managed_process(worker_cmd(), CONTROL_PLANE_ROOT, env) as worker:
                wait_for_http(f"{WORKER_URL}/missing", expected_status=404, process=worker)

                headers = {"Authorization": f"Bearer {API_KEY}"}
                create = httpx.post(f"{WORKER_URL}/sandbox/create", headers=headers, timeout=30)
                assert create.status_code == 200, create.text
                sandbox = create.json()

                write_file = httpx.post(
                    f"{WORKER_URL}/sandbox/{sandbox['sandbox_id']}/exec",
                    headers=headers,
                    json={
                        "command": [
                            "safe-run",
                            "run",
                            "python3",
                            "-c",
                            "from pathlib import Path; Path('f.txt').write_text('x', encoding='utf-8')",
                        ],
                        "timeout": 30,
                    },
                    timeout=60,
                )
                assert write_file.status_code == 200, write_file.text
                assert sse_events(write_file.text)[-1] == ("exit", {"code": 0})

                diff = httpx.post(
                    f"{WORKER_URL}/sandbox/{sandbox['sandbox_id']}/exec",
                    headers=headers,
                    json={"command": ["safe-run", "diff"], "timeout": 30},
                    timeout=60,
                )
                assert diff.status_code == 200, diff.text
                assert "created f.txt" in diff.text

                delete = httpx.delete(f"{WORKER_URL}/sandbox/{sandbox['sandbox_id']}", headers=headers, timeout=30)
                assert delete.status_code == 200, delete.text
                sandbox = None
    finally:
        if sandbox:
            try:
                docker_client.containers.get(sandbox["container_id"]).remove(force=True)
            except NotFound:
                pass


def docker_client_or_skip():
    """Return a Docker client when Docker and the sandbox image are available."""
    import docker

    try:
        client = docker.from_env()
        client.ping()
        client.images.get("saep-sandbox:local")
    except ImageNotFound:
        pytest.skip("saep-sandbox:local image is not built; run `make build` first")
    except DockerException as exc:
        pytest.skip(f"Docker is not available: {exc}")
    return client


def require_port_free(port: int) -> None:
    """Fail fast if a local development port is already occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            pytest.fail(f"127.0.0.1:{port} is already in use")


def local_env(tmp_path: Path) -> dict[str, str]:
    """Environment shared by the local orchestrator and Worker subprocesses."""
    env = os.environ.copy()
    env.update(
        {
            "SAEP_INTERNAL_TOKEN": INTERNAL_TOKEN,
            "SAEP_REGISTRY_DB": (tmp_path / "registry.sqlite3").as_posix(),
            "SAEP_WORKSPACES_DIR": (tmp_path / "workspaces").as_posix(),
            "SAEP_SANDBOX_IMAGE": "saep-sandbox:local",
        }
    )
    return env


def orchestrator_cmd() -> list[str]:
    """Command used to run the local FastAPI orchestrator."""
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "orchestrator.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "9999",
    ]


def worker_cmd() -> list[str]:
    """Command used to run the local Cloudflare Worker runtime."""
    return [
        "npx",
        "--yes",
        "wrangler@latest",
        "dev",
        "--ip",
        "127.0.0.1",
        "--port",
        "8787",
        "--local",
        "--show-interactive-dev-session=false",
        "--log-level",
        "error",
    ]


def wait_for_http(url: str, expected_status: int, process: subprocess.Popen, timeout: float = 45) -> None:
    """Poll a URL until it returns the expected status or the process exits."""
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            pytest.fail(f"process exited while waiting for {url}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == expected_status:
                return
            last_error = f"status={response.status_code} body={response.text[:200]}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(0.5)
    pytest.fail(f"timed out waiting for {url}: {last_error}")


def sse_events(body: str) -> list[tuple[str, dict]]:
    """Parse the small SSE subset emitted by the orchestrator."""
    events: list[tuple[str, dict]] = []
    for frame in body.strip().split("\n\n"):
        event_name = ""
        payload: dict | None = None
        for line in frame.splitlines():
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                payload = json.loads(line[len("data: ") :])
        if event_name and payload is not None:
            events.append((event_name, payload))
    return events


@contextmanager
def managed_process(command: list[str], cwd: Path, env: dict[str, str]) -> Iterator[subprocess.Popen]:
    """Start a subprocess and always terminate it at the end of the test."""
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        yield process
    finally:
        terminate_process(process)


def terminate_process(process: subprocess.Popen) -> None:
    """Terminate a subprocess group without leaving local dev servers running."""
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
