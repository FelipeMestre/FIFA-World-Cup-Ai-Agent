import { ApiError, sendChatMessage } from "@/lib/api/client";
import {
  streamChatEvents,
  type ChatStreamEvent,
} from "@/features/chat/api/stream-chat-events";

/**
 * Sends a chat message and yields the backend's SSE events (reasoning
 * deltas, content deltas, tool-call notices, cap-trip, terminal
 * `message_done`/`error`) as they arrive. Callers drive this async generator
 * to render the reply incrementally instead of waiting for one final blob --
 * see `use-chat-thread.ts`.
 */
export async function* sendMessage(
  conversationId: string | null,
  message: string,
): AsyncGenerator<ChatStreamEvent> {
  let response: Response;
  try {
    response = await sendChatMessage({ conversationId, message });
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("The chat assistant is temporarily unavailable", 502);
  }

  if (!response.body) {
    throw new ApiError("The chat assistant is temporarily unavailable", 502);
  }

  yield* streamChatEvents(response.body);
}
