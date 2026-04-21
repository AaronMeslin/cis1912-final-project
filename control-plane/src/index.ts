/**
 * Sandboxed Agent Execution Platform — Cloudflare Worker (stub).
 *
 * TODO: Integrate with real sandbox orchestration (Docker API, Nomad, k8s, or remote agent).
 * TODO: Authn/z (API tokens, mTLS) on all routes.
 * TODO: Durable Objects or Queues for session streaming and long-lived sandboxes.
 */

export interface Env {
  ENVIRONMENT: string;
  SANDBOX_ORCHESTRATOR_URL: string;
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function notFound(): Response {
  return jsonResponse({ error: "not_found", message: "No route matched" }, 404);
}

// TODO: Replace in-memory map with D1 / KV / external store for sandbox metadata.
const sandboxRegistry = new Map<string, { createdAt: string; status: string }>();

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    // POST /sandbox/create
    if (request.method === "POST" && path === "/sandbox/create") {
      // TODO: Call orchestrator to provision container / VM; persist id + credentials.
      const id = crypto.randomUUID();
      sandboxRegistry.set(id, {
        createdAt: new Date().toISOString(),
        status: "created",
      });
      return jsonResponse({
        sandboxId: id,
        status: "created",
        environment: env.ENVIRONMENT,
        orchestrator: env.SANDBOX_ORCHESTRATOR_URL,
      });
    }

    // DELETE /sandbox/:id
    const del = path.match(/^\/sandbox\/([^/]+)$/);
    if (request.method === "DELETE" && del) {
      const id = del[1];
      // TODO: Stop and remove backing sandbox; revoke credentials.
      const existed = sandboxRegistry.delete(id);
      if (!existed) {
        return jsonResponse({ error: "not_found", sandboxId: id }, 404);
      }
      return jsonResponse({ sandboxId: id, status: "destroyed" });
    }

    // GET /sandbox/:id/health
    const health = path.match(/^\/sandbox\/([^/]+)\/health$/);
    if (request.method === "GET" && health) {
      const id = health[1];
      const rec = sandboxRegistry.get(id);
      if (!rec) {
        return jsonResponse({ error: "not_found", sandboxId: id }, 404);
      }
      // TODO: Ping orchestrator / agent inside sandbox for CPU, memory, disk, process health.
      return jsonResponse({
        sandboxId: id,
        healthy: true,
        status: rec.status,
        createdAt: rec.createdAt,
        metrics: {
          cpuPercent: null,
          memoryBytes: null,
          diskBytes: null,
        },
      });
    }

    return notFound();
  },
};
