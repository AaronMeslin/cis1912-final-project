#!/usr/bin/env python3
"""Run the local SAEP demo task through the Worker API."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx
from docker.errors import DockerException, ImageNotFound

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE_ROOT = REPO_ROOT / "control-plane"
DEFAULT_WORKER_URL = "http://127.0.0.1:8787"
DEFAULT_ORCHESTRATOR_URL = "http://127.0.0.1:9999"
DEFAULT_API_KEY = "dev-api-key"
DEFAULT_INTERNAL_TOKEN = "dev-internal-token"
DEFAULT_SANDBOX_IMAGE = os.environ.get("SAEP_SANDBOX_IMAGE", "saep-sandbox:local")
DEMO_UPDATE_CODE = (
    "from pathlib import Path; "
    "index = Path('demo-frontend/index.html'); "
    "styles = Path('demo-frontend/styles.css'); "
    "index.write_text(index.read_text(encoding='utf-8').replace('Sandbox Demo', 'Sandbox Agent Demo'), encoding='utf-8'); "
    "styles.write_text(styles.read_text(encoding='utf-8').replace('#2563eb', '#7c3aed'), encoding='utf-8')"
)
DEMO_UPDATE_COMMAND = ["safe-run", "run", "python3", "-c", DEMO_UPDATE_CODE]
DIFF_COMMAND = ["safe-run", "diff"]
EXPECTED_DIFF_LINES = [
    "modified demo-frontend/index.html",
    "modified demo-frontend/styles.css",
]


class DemoTaskError(RuntimeError):
    """Raised when the demo task cannot complete cleanly."""


class ResponseLike(Protocol):
    """Small subset of httpx.Response used by the demo task runner."""

    status_code: int
    text: str

    def json(self) -> dict[str, Any]: ...


class ClientLike(Protocol):
    """Small subset of httpx.Client used by the demo task runner."""

    def post(self, url: str, **kwargs: Any) -> ResponseLike: ...

    def delete(self, url: str, **kwargs: Any) -> ResponseLike: ...


@dataclass(frozen=True)
class DemoTaskResult:
    """Result returned after a successful demo task run."""

    sandbox_id: str
    diff_output: str


def run_demo_task(client: ClientLike, worker_url: str, api_key: str, timeout: int) -> DemoTaskResult:
    """Create a sandbox, run the demo edit, return safe-run diff output, and clean up."""
    base_url = worker_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    sandbox: dict[str, Any] | None = None

    try:
        sandbox = _create_sandbox(client, base_url, headers)
        sandbox_id = str(sandbox["sandbox_id"])
        update_response = _exec_command(client, base_url, headers, sandbox_id, DEMO_UPDATE_COMMAND, timeout)
        update_events = parse_sse_events(update_response.text)
        _require_exit_code(update_events, 0, "demo update command")

        diff_response = _exec_command(client, base_url, headers, sandbox_id, DIFF_COMMAND, timeout)
        diff_output = output_from_sse(diff_response.text)
        _require_expected_diff(diff_output)
        return DemoTaskResult(sandbox_id=sandbox_id, diff_output=diff_output)
    finally:
        if sandbox is not None and "sandbox_id" in sandbox:
            _delete_sandbox(client, base_url, headers, str(sandbox["sandbox_id"]))


def parse_sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse the small SSE subset emitted by the orchestrator."""
    events: list[tuple[str, dict[str, Any]]] = []
    for frame in body.strip().split("\n\n"):
        event_name = ""
        payload: dict[str, Any] | None = None
        for line in frame.splitlines():
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                payload = json.loads(line[len("data: ") :])
        if event_name and payload is not None:
            events.append((event_name, payload))
    return events


def output_from_sse(body: str) -> str:
    """Extract stdout/stderr lines from orchestrator SSE output."""
    lines: list[str] = []
    for event_name, payload in parse_sse_events(body):
        if event_name == "output" and isinstance(payload.get("line"), str):
            lines.append(payload["line"])
    return "".join(lines)


def check_docker_image(image_name: str) -> Any:
    """Return a Docker client when Docker and the sandbox image are available."""
    import docker

    try:
        client = docker.from_env()
        client.ping()
        client.images.get(image_name)
    except ImageNotFound as exc:
        raise DemoTaskError(f"{image_name} image is not built; run `make build` first") from exc
    except DockerException as exc:
        raise DemoTaskError(f"Docker is not available: {exc}") from exc
    return client


def require_port_free(port: int) -> None:
    """Fail fast if a local development port is already occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise DemoTaskError(f"127.0.0.1:{port} is already in use")


def local_env(tmp_path: Path, internal_token: str, sandbox_image: str) -> dict[str, str]:
    """Environment shared by the local orchestrator and Worker subprocesses."""
    env = os.environ.copy()
    env.update(
        {
            "SAEP_INTERNAL_TOKEN": internal_token,
            "SAEP_REGISTRY_DB": (tmp_path / "registry.sqlite3").as_posix(),
            "SAEP_WORKSPACES_DIR": (tmp_path / "workspaces").as_posix(),
            "SAEP_WORKSPACE_SEED_DIR": REPO_ROOT.as_posix(),
            "SAEP_SANDBOX_IMAGE": sandbox_image,
        }
    )
    return env


def orchestrator_cmd() -> list[str]:
    """Command used to run the local FastAPI orchestrator."""
    return [sys.executable, "-m", "uvicorn", "orchestrator.main:app", "--host", "127.0.0.1", "--port", "9999"]


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
            raise DemoTaskError(f"process exited while waiting for {url}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == expected_status:
                return
            last_error = f"status={response.status_code} body={response.text[:200]}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise DemoTaskError(f"timed out waiting for {url}: {last_error}")


@contextmanager
def managed_process(command: list[str], cwd: Path, env: dict[str, str]) -> Iterator[subprocess.Popen]:
    """Start a subprocess and always terminate it at the end of the task."""
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


def _create_sandbox(client: ClientLike, base_url: str, headers: dict[str, str]) -> dict[str, Any]:
    response = client.post(f"{base_url}/sandbox/create", headers=headers, timeout=30)
    _require_success(response, "create sandbox")
    body = response.json()
    if not body.get("sandbox_id"):
        raise DemoTaskError(f"create sandbox response missing sandbox_id: {body}")
    return body


def _exec_command(
    client: ClientLike,
    base_url: str,
    headers: dict[str, str],
    sandbox_id: str,
    command: list[str],
    timeout: int,
) -> ResponseLike:
    response = client.post(
        f"{base_url}/sandbox/{sandbox_id}/exec",
        headers=headers,
        json={"command": command, "timeout": timeout},
        timeout=timeout + 30,
    )
    _require_success(response, f"exec {' '.join(command[:2])}")
    return response


def _delete_sandbox(client: ClientLike, base_url: str, headers: dict[str, str], sandbox_id: str) -> None:
    response = client.delete(f"{base_url}/sandbox/{sandbox_id}", headers=headers, timeout=30)
    _require_success(response, "delete sandbox")


def _require_success(response: ResponseLike, label: str) -> None:
    if response.status_code >= 400:
        raise DemoTaskError(f"{label} failed with HTTP {response.status_code}: {response.text}")


def _require_exit_code(events: list[tuple[str, dict[str, Any]]], expected: int, label: str) -> None:
    if not events:
        raise DemoTaskError(f"{label} returned no SSE events")
    event_name, payload = events[-1]
    if event_name != "exit" or payload.get("code") != expected:
        raise DemoTaskError(f"{label} exited unexpectedly: events={events}")


def _require_expected_diff(diff_output: str) -> None:
    missing = [line for line in EXPECTED_DIFF_LINES if line not in diff_output]
    if missing:
        raise DemoTaskError(f"safe-run diff did not include expected demo changes; missing={missing}; output={diff_output!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the SAEP demo task through the local Worker API.")
    parser.add_argument("--sandbox-image", default=DEFAULT_SANDBOX_IMAGE, help="Sandbox image to run")
    parser.add_argument("--timeout", type=int, default=30, help="Command timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        check_docker_image(args.sandbox_image)
        require_port_free(9999)
        require_port_free(8787)
        with tempfile.TemporaryDirectory(prefix="saep-demo-task-") as tmp:
            env = local_env(Path(tmp), DEFAULT_INTERNAL_TOKEN, args.sandbox_image)
            with managed_process(orchestrator_cmd(), CONTROL_PLANE_ROOT, env) as orchestrator:
                wait_for_http(f"{DEFAULT_ORCHESTRATOR_URL}/healthz", expected_status=200, process=orchestrator)
                with managed_process(worker_cmd(), CONTROL_PLANE_ROOT, env) as worker:
                    wait_for_http(f"{DEFAULT_WORKER_URL}/missing", expected_status=404, process=worker)
                    with httpx.Client() as client:
                        result = run_demo_task(client, DEFAULT_WORKER_URL, DEFAULT_API_KEY, args.timeout)
                    print(result.diff_output, end="")
    except (DemoTaskError, httpx.HTTPError) as exc:
        print(f"run-demo-task failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
