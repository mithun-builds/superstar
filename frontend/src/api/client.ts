// Tiny fetch wrapper.
//
// - Sends cookies (session auth via Django) and the CSRF token on mutations.
// - Adds X-Org-Slug from the current org context when one is provided.
// - Throws an `ApiError` with status + body on non-2xx responses so callers
//   can branch on `.status` without parsing twice.

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API ${status}`);
    this.status = status;
    this.body = body;
  }
}

const CSRF_COOKIE = "csrftoken";

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

export interface ApiOptions {
  method?: string;
  body?: unknown;
  orgSlug?: string;
}

export async function api<T>(path: string, opts: ApiOptions = {}): Promise<T> {
  const method = (opts.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = { Accept: "application/json" };

  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (opts.orgSlug) {
    headers["X-Org-Slug"] = opts.orgSlug;
  }
  if (method !== "GET" && method !== "HEAD") {
    const csrf = getCookie(CSRF_COOKIE);
    if (csrf) headers["X-CSRFToken"] = csrf;
  }

  const resp = await fetch(path, {
    method,
    credentials: "include",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  // 204 No Content — no body to parse.
  if (resp.status === 204) return undefined as T;

  let parsed: unknown;
  const text = await resp.text();
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = text;
  }

  if (!resp.ok) {
    throw new ApiError(resp.status, parsed);
  }
  return parsed as T;
}
