/**
 * Small typed fetch wrapper for client components. Calls our own Next.js
 * Route Handlers (`/api/auth/login`, `/api/conversations`) -- never the
 * FastAPI backend directly, and never sees the bearer token. The live
 * conversation stream is opened by `connectConversationEvents`, a plain
 * `EventSource` against a Route Handler that holds the session cookie and
 * proxies the backend's SSE response through.
 */

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  const fallback = `Request failed with status ${response.status}`;
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export interface LoginPayload {
  email: string;
  password: string;
}

export async function login(payload: LoginPayload): Promise<void> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/auth/logout", { method: "POST" });
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
}

/**
 * JSON fetch against our own Route Handlers. Throws `ApiError` on a
 * non-2xx so feature clients don't each reimplement status parsing.
 */
export async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }
  return (await response.json()) as T;
}
