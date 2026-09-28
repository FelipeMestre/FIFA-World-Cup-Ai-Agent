import { fetchJson } from "@/lib/api/client";

export interface SendMessageResult {
  conversationId: string;
  messageId: number;
}

/** The selected Match chip, forwarded to the backend so it can resolve the
 * match and inject a directive tool-use instruction for the agent.
 */
export interface SendMessageContext {
  matchId: number;
}

interface SendMessageResponseDto {
  conversation_id: string;
  message_id: number;
}

/**
 * `POST /conversations/{id}/messages` via our own Next.js proxy route. A
 * 202 ack -- the reply itself streams in separately over the conversation's
 * open SSE connection (`connectConversationEvents`). `fetchJson` throws
 * `ApiError` on a non-2xx (403 not-owned, 409 turn-already-in-progress),
 * which replaces the old WS `rejected` event as the failure signal.
 */
export async function sendMessage(
  conversationId: string,
  content: string,
  context?: SendMessageContext,
): Promise<SendMessageResult> {
  const payload = await fetchJson<SendMessageResponseDto>(
    `/api/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(
        context ? { content, context: { match_id: context.matchId } } : { content },
      ),
    },
  );
  return { conversationId: payload.conversation_id, messageId: payload.message_id };
}
