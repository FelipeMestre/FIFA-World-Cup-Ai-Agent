import { NextResponse } from "next/server";

import { BACKEND_API_URL } from "@/lib/api/config";
import { getSessionToken } from "@/lib/auth/session";

/**
 * Proxies to the FastAPI backend's `/chat/messages`, attaching the JWT from
 * the httpOnly session cookie server-side. The browser never sees the
 * backend's URL or the bearer token.
 *
 * The backend streams its reply over Server-Sent Events, so this handler
 * pipes `backendResponse.body` through unchanged instead of awaiting/parsing
 * a full JSON body -- `EventSource` can't be used here since it only
 * supports GET and this proxy must forward a JWT via POST.
 */
export async function POST(request: Request) {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  let body: { conversation_id?: string | null; message?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  if (!body.message || body.message.trim().length === 0) {
    return NextResponse.json({ detail: "Message is required" }, { status: 400 });
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_API_URL}/chat/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        conversation_id: body.conversation_id ?? null,
        message: body.message,
      }),
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach the World Cup AI Scout backend" },
      { status: 502 },
    );
  }

  if (!backendResponse.ok || !backendResponse.body) {
    const payload = await backendResponse.json().catch(() => null);
    return NextResponse.json(
      { detail: payload?.detail ?? "The chat assistant is unavailable" },
      { status: backendResponse.status },
    );
  }

  return new Response(backendResponse.body, {
    status: backendResponse.status,
    headers: { "Content-Type": "text/event-stream" },
  });
}
