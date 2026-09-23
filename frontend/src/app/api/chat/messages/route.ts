import { NextResponse } from "next/server";

import { isConversationId } from "@/features/chat/conversation-id";
import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/**
 * Proxies `POST /chat/messages`: persists the user's message and enqueues
 * background reply generation -- returns an ack, not a stream. Callers
 * connect to `GET /api/conversations/{id}/watch` right after this resolves
 * to observe the reply (see `features/chat/api/send-message.ts`).
 */
export async function POST(request: Request) {
  let body: { conversation_id?: string | null; message?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  if (!body.message || body.message.trim().length === 0) {
    return NextResponse.json({ detail: "Message is required" }, { status: 400 });
  }

  if (!body.conversation_id || !isConversationId(body.conversation_id)) {
    return NextResponse.json({ detail: "conversation_id is required" }, { status: 400 });
  }

  return proxyBackendJson("/chat/messages", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: body.conversation_id,
      message: body.message,
    }),
  });
}
