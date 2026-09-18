import { ApiError, sendChatMessage } from "@/lib/api/client";
import { messagePartSchema } from "@/features/chat/schemas/message-part.schema";
import type { MessagePart } from "@/features/chat/types";

export interface SendMessageResult {
  conversationId: string;
  parts: MessagePart[];
}

/**
 * Sends a chat message and validates the reply's parts against the widget
 * contract schema. A part that fails validation (e.g. a future
 * `team_widget` whose `data` shape doesn't match yet) is dropped rather than
 * crashing the thread -- see message-part-renderer.tsx for the visible
 * fallback shown to the user in that case.
 */
export async function sendMessage(
  conversationId: string | null,
  message: string,
): Promise<SendMessageResult> {
  try {
    const response = await sendChatMessage({ conversationId, message });
    const parts: MessagePart[] = [];

    for (const rawPart of response.reply.parts) {
      const result = messagePartSchema.safeParse(rawPart);
      if (result.success) {
        parts.push(result.data);
      }
    }

    return { conversationId: response.conversation_id, parts };
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("The chat assistant is temporarily unavailable", 502);
  }
}
