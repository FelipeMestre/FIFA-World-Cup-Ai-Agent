import { NextResponse } from "next/server";

import { CONVERSATION_TITLE_MAX_LENGTH, isConversationId } from "@/features/chat/conversation-id";
import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `PATCH /conversations/{id}` (title rename). */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> },
) {
  const { conversationId } = await params;
  if (!isConversationId(conversationId)) {
    return NextResponse.json({ detail: "Conversation not found" }, { status: 404 });
  }

  let body: { title?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  const title = body.title?.trim();
  if (!title) {
    return NextResponse.json({ detail: "Title is required" }, { status: 400 });
  }
  if (title.length > CONVERSATION_TITLE_MAX_LENGTH) {
    return NextResponse.json({ detail: "Title is too long" }, { status: 400 });
  }

  return proxyBackendJson(`/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}
