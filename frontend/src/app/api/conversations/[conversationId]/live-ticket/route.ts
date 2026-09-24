import { NextResponse } from "next/server";

import { isConversationId } from "@/features/chat/conversation-id";
import { BACKEND_API_URL } from "@/lib/api/config";
import { getSessionToken } from "@/lib/auth/session";

const CHAT_WS_PUBLIC_URL = process.env.CHAT_WS_PUBLIC_URL ?? "ws://localhost:8000/api/v1";

/**
 * Mints a one-time ticket and returns the browser-facing websocket URL.
 * The session JWT stays in the httpOnly cookie; the page never reads it.
 */
export async function POST(
  _request: Request,
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

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_API_URL}/chat/ws-tickets`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "Could not reach the World Cup AI Scout backend" }, { status: 502 });
  }

  const payload = (await backendResponse.json().catch(() => null)) as { ticket?: string; detail?: string } | null;
  if (!backendResponse.ok || !payload?.ticket) {
    return NextResponse.json(
      { detail: payload?.detail ?? "Could not open the live conversation" },
      { status: backendResponse.status || 502 },
    );
  }

  const url = new URL(`${CHAT_WS_PUBLIC_URL}/conversations/${conversationId}/live`);
  url.searchParams.set("ticket", payload.ticket);
  return NextResponse.json({ url: url.toString() });
}
