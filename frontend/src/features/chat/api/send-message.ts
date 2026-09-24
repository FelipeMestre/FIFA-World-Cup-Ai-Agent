import { ApiError, sendChatMessage, watchConversation } from "@/lib/api/client";
import {
  readChatStreamFrames,
  type ChatStreamEvent,
} from "@/features/chat/api/stream-chat-events";

const TERMINAL_EVENT_TYPES: ReadonlySet<ChatStreamEvent["type"]> = new Set([
  "message_done",
  "error",
]);

function toApiError(error: unknown): ApiError {
  return error instanceof ApiError
    ? error
    : new ApiError("The chat assistant is temporarily unavailable", 502);
}

/**
 * Sends a chat message (persisted synchronously; the reply generates as a
 * background job -- see the backend's `chat_router.py`), then attaches to
 * `GET /conversations/{id}/watch?after={stream_cursor}` and yields the backend's SSE events
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
  let after: string;
  try {
    const ack = await sendChatMessage({ conversationId, message }, signal);
    after = ack.streamCursor;
  } catch (error) {
    throw toApiError(error);
  }

  let resumed = false;
  for (;;) {
    let response: Response;
    try {
      response = await watchConversation(conversationId, signal, after);
    } catch (error) {
      throw toApiError(error);
    }

    if (response.status === 204 || !response.body) {
      // A 204 on the first watch means the turn ended before this request
      // landed. A 204 on a resume means the reply was consolidated after
      // the cursor we already rendered -- the saved messages have the rest.
      if (resumed) {
        return;
      }
      throw new ApiError("The chat assistant is temporarily unavailable", 502);
    }

    let lastId: string | null = null;
    let sawTerminal = false;
    for await (const frame of readChatStreamFrames(response.body)) {
      if (frame.id) {
        lastId = frame.id;
      }
      if (TERMINAL_EVENT_TYPES.has(frame.event.type)) {
        sawTerminal = true;
      }
      yield frame.event;
    }

    if (sawTerminal || !lastId || lastId === after) {
      return;
    }
    after = lastId;
    resumed = true;
  }
}
