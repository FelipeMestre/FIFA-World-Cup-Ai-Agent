import { NextResponse } from "next/server";

import { isConversationId } from "@/features/chat/conversation-id";
import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `GET /conversations/{id}/messages` (full replay, never Redis). */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ conversationId: string }> },
) {
  const { conversationId } = await params;
  if (!isConversationId(conversationId)) {
    return NextResponse.json({ detail: "Conversation not found" }, { status: 404 });
  }

  return proxyBackendJson(`/conversations/${conversationId}/messages`);
}

/**
 * Proxies `POST /conversations/{id}/messages` (send). 202 ack only -- the
 * reply itself streams in separately over `GET /conversations/{id}/events`.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> },
) {
  const { conversationId } = await params;
  if (!isConversationId(conversationId)) {
    return NextResponse.json({ detail: "Conversation not found" }, { status: 404 });
  }

  return proxyBackendJson(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify(await request.json()),
  });
}
