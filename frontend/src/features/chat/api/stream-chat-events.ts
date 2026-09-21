import type { RawMessagePart } from "@/features/chat/schemas/message-part.schema";

/**
 * The backend's SSE event vocabulary (`ChatStreamEventType` in
 * `backend/src/infra/openrouter/schemas.py`). Each wire frame is
 * `event: {type}\ndata: {json}\n\n`; the `data:` JSON never repeats `type`.
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

/**
 * A widget-producing tool call resolved inside the loop -- sent before the
 * model's final text finishes streaming, so the widget can render without
 * waiting for the rest of the turn. `part` is the same shape a
 * `message_done` event's `parts` will carry for this widget.
 */
export interface WidgetReadyEvent {
  type: "widget_ready";
  part: RawMessagePart;
}

/**
 * The tool-execution loop's iteration cap tripped. `content` is the
 * best-effort partial text accumulated so far (not a delta); `clarification`
 * is the ask to show the user, rendered as a distinct inline note. Always
 * immediately followed by a `message_done` event.
 */
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

const KNOWN_EVENT_TYPES: ReadonlySet<ChatStreamEvent["type"]> = new Set([
  "reasoning_delta",
  "content_delta",
  "tool_call",
  "widget_ready",
  "cap_reached",
  "message_done",
  "error",
]);

function isKnownEventType(value: string): value is ChatStreamEvent["type"] {
  return KNOWN_EVENT_TYPES.has(value as ChatStreamEvent["type"]);
}

function parseFrame(frame: string): ChatStreamEvent | null {
  let eventType: string | null = null;
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  if (!eventType || dataLines.length === 0 || !isKnownEventType(eventType)) {
    return null;
  }

  const data = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
  return { type: eventType, ...data } as ChatStreamEvent;
}

/**
 * Reads a `text/event-stream` body and yields typed events as SSE frames
 * arrive, splitting on the blank-line frame terminator. A manual reader is
 * required (instead of `EventSource`) because the Next.js route handler is a
 * JWT-bearing POST proxy, and `EventSource` only supports GET -- see
 * design.md's "SSE frontend consumption" decision.
 */
export async function* streamChatEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<ChatStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (value) {
        buffer += decoder.decode(value, { stream: true });
      }

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawFrame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = parseFrame(rawFrame);
        if (event) {
          yield event;
        }
        boundary = buffer.indexOf("\n\n");
      }

      if (done) {
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
