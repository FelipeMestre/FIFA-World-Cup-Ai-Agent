/**
 * Small typed fetch wrapper for client components. Calls our own Next.js
 * Route Handlers (`/api/auth/login`, `/api/chat/messages`) -- never the
 * FastAPI backend directly, and never sees the bearer token.
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

export interface SendChatMessagePayload {
  conversationId: string | null;
  message: string;
}

/**
 * Sends a chat message and returns the raw streaming `Response` -- the
 * backend replies over Server-Sent Events (`text/event-stream`), not one
 * final JSON blob. Callers read `.body` themselves (see
 * `features/chat/api/stream-chat-events.ts`).
 */
export async function sendChatMessage(payload: SendChatMessagePayload): Promise<Response> {
  const response = await fetch("/api/chat/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: payload.conversationId,
      message: payload.message,
    }),
  });

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }

  return response;
}
