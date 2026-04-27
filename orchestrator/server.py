from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .docker import DockerSandboxManager, SandboxNotFound


def route_request(
    method: str,
    path: str,
    _body: bytes,
    manager: DockerSandboxManager,
) -> tuple[int, dict]:
    if method == "POST" and path == "/sandboxes":
        try:
            return 201, manager.create()
        except RuntimeError as exc:
            return 502, {"error": "orchestrator_error", "message": str(exc)}

    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "sandboxes" and method == "DELETE":
        sandbox_id = parts[1]
        try:
            return 200, manager.destroy(sandbox_id)
        except SandboxNotFound:
            return 404, {"error": "not_found", "sandboxId": sandbox_id}

    if len(parts) == 3 and parts[0] == "sandboxes" and parts[2] == "health" and method == "GET":
        sandbox_id = parts[1]
        try:
            return 200, manager.health(sandbox_id)
        except SandboxNotFound:
            return 404, {"error": "not_found", "sandboxId": sandbox_id}

    return 404, {"error": "not_found"}


class OrchestratorHandler(BaseHTTPRequestHandler):
    manager = DockerSandboxManager()

    def do_POST(self) -> None:
        self._handle()

    def do_GET(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def _handle(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length) if length else b""
        status, payload = route_request(self.command, self.path, body, self.manager)
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    port = int(os.environ.get("SAEP_ORCHESTRATOR_PORT", "9999"))
    server = ThreadingHTTPServer(("127.0.0.1", port), OrchestratorHandler)
    print(f"SAEP orchestrator listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
