import { NextResponse } from "next/server";

import { isConversationId } from "@/features/chat/conversation-id";
import { BACKEND_API_URL } from "@/lib/api/config";
import { getSessionToken } from "@/lib/auth/session";

/**
 * Proxies `GET /conversations/{id}/watch`: reattaches to a background
 * turn's Server-Sent Events stream, or 204 if none is currently in
 * progress. Streamed through unchanged, same rationale as the old
 * `/chat/messages` streaming proxy this replaces used to have --
 * `EventSource` can't attach a bearer token, so a manual pass-through
 * Route Handler is needed either way.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> },
) {
  const { conversationId } = await params;
  if (!isConversationId(conversationId)) {
    return NextResponse.json({ detail: "Conversation not found" }, { status: 404 });
  }

  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const after = new URL(request.url).searchParams.get("after");
  const watchUrl = new URL(`${BACKEND_API_URL}/conversations/${conversationId}/watch`);
  if (after) {
    watchUrl.searchParams.set("after", after);
  }
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const lastEventId = request.headers.get("Last-Event-ID");
  if (lastEventId) {
    headers["Last-Event-ID"] = lastEventId;
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(watchUrl, { headers });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach the World Cup AI Scout backend" },
      { status: 502 },
    );
  }

  if (backendResponse.status === 204) {
    return new Response(null, { status: 204 });
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
