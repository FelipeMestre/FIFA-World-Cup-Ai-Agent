import type { RawMessagePart } from "@/features/chat/schemas/message-part.schema";

/**
 * Wire events for the conversation SSE stream (`GET /conversations/{id}/events`,
 * proxied through `app/api/conversations/[conversationId]/events/route.ts`).
 * The reply vocabulary matches the Redis stream entries `generate_chat_reply_task`
 * publishes on `event: turn` frames; `conversation_updated` frames carry the
 * background categorization job's result on `event: conversation_updated`
 * frames -- both share one connection per `_conversation_events` in the
 * backend's `conversation_router.py`.
 */

export interface ReasoningDeltaEvent {
  type: "reasoning_delta";
  content: string;
}

export interface ContentDeltaEvent {
  type: "content_delta";
  content: string;
}

export interface ToolCallEvent {
  type: "tool_call";
  name: string;
}

export interface WidgetReadyEvent {
  type: "widget_ready";
  part: RawMessagePart;
}

export interface CapReachedEvent {
  type: "cap_reached";
  content: string;
  clarification: string;
}

export interface MessageDoneEvent {
  type: "message_done";
  conversation_id: string;
  parts: RawMessagePart[];
  model: string | null;
}

export interface ErrorEvent {
  type: "error";
  detail: string;
}

export type ChatStreamEvent =
  | ReasoningDeltaEvent
  | ContentDeltaEvent
  | ToolCallEvent
  | WidgetReadyEvent
  | CapReachedEvent
  | MessageDoneEvent
  | ErrorEvent;

export interface UserMessageEvent {
  type: "user_message";
  content: string;
  message_id: number;
  conversation_id: string;
  title: string;
  cursor: string;
}

/**
 * Emitted on the `conversation_updated` SSE event once
 * `categorize_conversation_task` resolves a title + icon for a conversation
 * -- delivered to every device with this conversation's SSE connection
 * open, regardless of which conversation is on screen there (the backend
 * reads it off the requesting user's own per-user stream, not this one's
 * turn stream).
 */
export interface ConversationUpdatedEvent {
  type: "conversation_updated";
  conversation_id: string;
  title: string;
  icon: string;
  cursor: string;
}

export type ConversationEvent =
  | (ChatStreamEvent & { cursor?: string })
  | UserMessageEvent
  | ConversationUpdatedEvent;

export interface EventsConnection {
  conversationId: string;
  close: () => void;
}

/**
 * Opens the SSE connection for one conversation. `EventSource` reconnects
 * natively on a drop and the backend resumes from the last delivered id via
 * the `Last-Event-ID` header it sends automatically -- no hand-rolled
 * reconnect loop, pending-send queue, or client-side cursor/dedup tracking
 * needed (all of that existed only for the old WebSocket, which had none of
 * this built in).
 *
 * Hits our own Next.js proxy route, never the FastAPI backend directly:
 * `EventSource` cannot set an `Authorization` header, so the proxy route
 * holds the session cookie server-side instead.
 */
export function connectConversationEvents(
  conversationId: string,
  onEvent: (event: ConversationEvent) => void,
): EventsConnection {
  const source = new EventSource(`/api/conversations/${conversationId}/events`);

  const handleFrame = (message: MessageEvent<string>) => {
    try {
      onEvent(JSON.parse(message.data) as ConversationEvent);
    } catch {
      // Ignore a frame that is not the JSON vocabulary above.
    }
  };

  source.addEventListener("turn", handleFrame);
  source.addEventListener("conversation_updated", handleFrame);

  return {
    conversationId,
    close() {
      source.close();
    },
  };
}
