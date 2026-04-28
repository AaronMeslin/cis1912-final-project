/**
 * Sandboxed Agent Execution Platform — Cloudflare Worker.
 *
 * The Worker is the public control-plane API. It authenticates callers and
 * proxies sandbox operations to the local Docker orchestrator.
 */

export interface Env {
  ENVIRONMENT: string;
  SANDBOX_ORCHESTRATOR_URL: string;
  API_KEY: string;
  ORCHESTRATOR_TOKEN?: string;
}

const SANDBOX_ROUTES = [
  { method: "POST", pattern: /^\/sandbox\/create$/ },
  { method: "GET", pattern: /^\/sandbox\/[^/]+\/health$/ },
  { method: "POST", pattern: /^\/sandbox\/[^/]+\/exec$/ },
  { method: "DELETE", pattern: /^\/sandbox\/[^/]+$/ },
];

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function notFound(): Response {
  return jsonResponse({ error: "not_found", message: "No route matched" }, 404);
}

function isSandboxRoute(method: string, path: string): boolean {
  return SANDBOX_ROUTES.some((route) => route.method === method && route.pattern.test(path));
}

function isAuthorized(request: Request, env: Env): boolean {
  const expected = `Bearer ${env.API_KEY}`;
  return Boolean(env.API_KEY) && request.headers.get("authorization") === expected;
}

function proxyHeaders(request: Request, env: Env): Headers {
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (accept) {
    headers.set("accept", accept);
  }
  if (env.ORCHESTRATOR_TOKEN) {
    headers.set("x-saep-internal-token", env.ORCHESTRATOR_TOKEN);
  }
  return headers;
}

function orchestratorUrl(request: Request, env: Env): string {
  const requestUrl = new URL(request.url);
  const base = env.SANDBOX_ORCHESTRATOR_URL.replace(/\/+$/, "");
  return `${base}${requestUrl.pathname}${requestUrl.search}`;
}

async function proxyToOrchestrator(request: Request, env: Env): Promise<Response> {
  const init: RequestInit = {
    method: request.method,
    headers: proxyHeaders(request, env),
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
  };

  let upstream: Response;
  try {
    upstream = await fetch(orchestratorUrl(request, env), init);
  } catch (_error) {
    return jsonResponse(
      {
        error: "orchestrator_unavailable",
        message: "Could not reach sandbox orchestrator",
      },
      502,
    );
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: upstream.headers,
  });
}

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    if (!isSandboxRoute(request.method, url.pathname)) {
      return notFound();
    }
    if (!isAuthorized(request, env)) {
      return jsonResponse({ error: "unauthorized", message: "Missing or invalid API key" }, 401);
    }
    return proxyToOrchestrator(request, env);
  },
};
