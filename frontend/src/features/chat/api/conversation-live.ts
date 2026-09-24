import { ApiError, fetchJson } from "@/lib/api/client";
import type { RawMessagePart } from "@/features/chat/schemas/message-part.schema";

/**
 * Wire events for the conversation websocket. The reply vocabulary matches
 * the Redis stream entries `generate_chat_reply_task` publishes.
 * `user_message` is written when a send is accepted, so every open client
 * sees it. `rejected` is delivered only to the socket that sent.
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

export interface RejectedEvent {
  type: "rejected";
  detail: string;
}

export type LiveServerEvent = (ChatStreamEvent & { cursor?: string }) | UserMessageEvent | RejectedEvent;

export interface LiveConnection {
  conversationId: string;
  send: (message: string) => void;
  close: () => void;
  isClosed: () => boolean;
}

const MAX_RECONNECTS = 5;
const RECONNECT_DELAY_MS = 500;

/**
 * Exclusive Redis stream ids (`milliseconds-sequence`). An id at or before
 * `seen` was already applied on this client.
 */
export function isCursorAtOrBefore(cursor: string, seen: string): boolean {
  const [cursorMs, cursorSeq] = cursor.split("-").map(Number);
  const [seenMs, seenSeq] = seen.split("-").map(Number);
  if (cursorMs !== seenMs) return cursorMs < seenMs;
  return cursorSeq <= seenSeq;
}

/**
 * Opens the live socket for one conversation and keeps it open across
 * drops. Sends queue until the socket is open. The session cookie stays
 * on the Next origin: this asks our Route Handler for a one-time ticket
 * and connects to the URL it returns.
 */
export function connectConversationLive(
  conversationId: string,
  onEvent: (event: LiveServerEvent) => void,
): LiveConnection {
  let closed = false;
  let socket: WebSocket | null = null;
  let reconnects = 0;
  const pending: string[] = [];

  const failPending = (detail: string) => {
    if (pending.length === 0) return;
    pending.length = 0;
    onEvent({ type: "error", detail });
  };

  const open = async () => {
    if (closed) return;
    let url: string;
    try {
      const body = await fetchJson<{ url: string }>(
        `/api/conversations/${conversationId}/live-ticket`,
        { method: "POST" },
      );
      url = body.url;
    } catch (error) {
      failPending(error instanceof ApiError ? error.message : "Could not open the live conversation");
      return;
    }
    if (closed) return;

    const next = new WebSocket(url);
    socket = next;
    next.onopen = () => {
      reconnects = 0;
      if (socket !== next) return;
      for (const payload of pending.splice(0)) next.send(payload);
    };
    next.onmessage = (message) => {
      try {
        onEvent(JSON.parse(String(message.data)) as LiveServerEvent);
      } catch {
        // Ignore a frame that is not the JSON vocabulary above.
      }
    };
    next.onclose = () => {
      if (socket === next) socket = null;
      if (closed || reconnects >= MAX_RECONNECTS) return;
      reconnects += 1;
      window.setTimeout(() => void open(), RECONNECT_DELAY_MS);
    };
  };

  void open();

  return {
    conversationId,
    isClosed: () => closed,
    close() {
      closed = true;
      pending.length = 0;
      socket?.close();
    },
    send(message: string) {
      const payload = JSON.stringify({ type: "send", message });
      if (socket?.readyState === WebSocket.OPEN) socket.send(payload);
      else pending.push(payload);
    },
  };
}
