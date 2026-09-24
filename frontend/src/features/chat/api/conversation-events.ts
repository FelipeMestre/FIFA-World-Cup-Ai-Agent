import type { RawMessagePart } from "@/features/chat/schemas/message-part.schema";

/**
 * Wire events for the conversation SSE stream (`GET /conversations/{id}/events`,
 * proxied through `app/api/conversations/[conversationId]/events/route.ts`).
 * This connection is turn-stream-only: it carries the reply vocabulary that
 * matches the Redis stream entries `generate_chat_reply_task` publishes on
 * `event: turn` frames. Account-wide events (`conversation_created`,
 * `conversation_updated`) travel over the separate per-user connection --
 * see `@/features/chat/api/user-events`.
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

export type ConversationEvent = (ChatStreamEvent & { cursor?: string }) | UserMessageEvent;

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

  return {
    conversationId,
    close() {
      source.close();
    },
  };
}
