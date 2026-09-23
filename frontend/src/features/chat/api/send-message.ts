import { ApiError, sendChatMessage, watchConversation } from "@/lib/api/client";
import {
  streamChatEvents,
  type ChatStreamEvent,
} from "@/features/chat/api/stream-chat-events";

function toApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError("The chat assistant is temporarily unavailable", 502);
}

/**
 * Sends a chat message (persisted synchronously; the reply generates as a
 * background job -- see the backend's `chat_router.py`), then attaches to
 * `GET /conversations/{id}/watch` and yields the backend's SSE events
 * (reasoning deltas, content deltas, tool-call notices, cap-trip, terminal
 * `message_done`/`error`) as they arrive. Callers drive this async generator
 * to render the reply incrementally instead of waiting for one final blob --
 * see `use-chat-thread.ts`.
 */
export async function* sendMessage(
  conversationId: string,
  message: string,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  try {
    await sendChatMessage({ conversationId, message }, signal);
  } catch (error) {
    throw toApiError(error);
  }

  let response: Response;
  try {
    response = await watchConversation(conversationId, signal);
  } catch (error) {
    throw toApiError(error);
  }

  if (response.status === 204 || !response.body) {
    // The backend reserves the in-progress flag synchronously before
    // acking the send above, so watch should always have something to
    // stream right after it. A 204 here means the turn already finished
    // (or failed) faster than this second request landed -- either way,
    // there is no live stream left to show.
    throw new ApiError("The chat assistant is temporarily unavailable", 502);
  }

  yield* streamChatEvents(response.body);
}
