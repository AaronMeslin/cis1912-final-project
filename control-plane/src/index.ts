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

async function orchestratorRequest(env: Env, path: string, init: RequestInit = {}): Promise<Response> {
  if (!env.SANDBOX_ORCHESTRATOR_URL) {
    return jsonResponse({ error: "upstream_not_configured" }, 503);
  }

  const baseUrl = env.SANDBOX_ORCHESTRATOR_URL.replace(/\/+$/, "");
  try {
    const upstream = await fetch(`${baseUrl}${path}`, init);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json; charset=utf-8" },
    });
  } catch (error) {
    return jsonResponse({ error: "upstream_unavailable", message: String(error) }, 502);
  }
}

export default {
  async fetch(request: Request, env: Env, _ctx: unknown): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "POST" && path === "/sandbox/create") {
      return orchestratorRequest(env, "/sandboxes", { method: "POST" });
    }

    const del = path.match(/^\/sandbox\/([^/]+)$/);
    if (request.method === "DELETE" && del) {
      const id = del[1];
      return orchestratorRequest(env, `/sandboxes/${id}`, { method: "DELETE" });
    }

    const health = path.match(/^\/sandbox\/([^/]+)\/health$/);
    if (request.method === "GET" && health) {
      const id = health[1];
      return orchestratorRequest(env, `/sandboxes/${id}/health`, { method: "GET" });
    }

    return notFound();
  },
};
