import { describe, expect, it } from "vitest";

import { streamChatEvents } from "@/features/chat/api/stream-chat-events";

/** Builds a `ReadableStream<Uint8Array>` from one or more SSE frame strings. */
function sseStream(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const events = [];
  for await (const event of streamChatEvents(stream)) {
    events.push(event);
  }
  return events;
}

describe("streamChatEvents", () => {
  it("parses a sequence of reasoning_delta, content_delta, and message_done frames in order", async () => {
    const stream = sseStream([
      'event: reasoning_delta\ndata: {"content": "Checking the time"}\n\n',
      'event: content_delta\ndata: {"content": "It is currently"}\n\n',
      'event: content_delta\ndata: {"content": " 10am UTC."}\n\n',
      'event: message_done\ndata: {"conversation_id": "conv-1", "parts": [{"type": "text", "content": "It is currently 10am UTC."}], "model": "anthropic/claude-sonnet-4.5"}\n\n',
    ]);

    const events = await collect(stream);

    expect(events).toEqual([
      { type: "reasoning_delta", content: "Checking the time" },
      { type: "content_delta", content: "It is currently" },
      { type: "content_delta", content: " 10am UTC." },
      {
        type: "message_done",
        conversation_id: "conv-1",
        parts: [{ type: "text", content: "It is currently 10am UTC." }],
        model: "anthropic/claude-sonnet-4.5",
      },
    ]);
  });

  it("parses a tool_call frame", async () => {
    const stream = sseStream([
      'event: tool_call\ndata: {"name": "get_current_utc_time"}\n\n',
    ]);

    const events = await collect(stream);

    expect(events).toEqual([{ type: "tool_call", name: "get_current_utc_time" }]);
  });

  it("parses a cap_reached frame followed by message_done", async () => {
    const stream = sseStream([
      'event: cap_reached\ndata: {"content": "Based on what I found so far...", "clarification": "Could you clarify what you are looking for?"}\n\n',
      'event: message_done\ndata: {"conversation_id": "conv-2", "parts": [{"type": "text", "content": "Based on what I found so far... Could you clarify what you are looking for?"}], "model": null}\n\n',
    ]);

    const events = await collect(stream);

    expect(events[0]).toEqual({
      type: "cap_reached",
      content: "Based on what I found so far...",
      clarification: "Could you clarify what you are looking for?",
    });
    expect(events[1].type).toBe("message_done");
  });

  it("parses an error frame", async () => {
    const stream = sseStream([
      'event: error\ndata: {"detail": "The chat assistant is temporarily unavailable"}\n\n',
    ]);

    const events = await collect(stream);

    expect(events).toEqual([
      { type: "error", detail: "The chat assistant is temporarily unavailable" },
    ]);
  });

  it("handles a frame split across multiple stream chunks", async () => {
    const stream = sseStream([
      'event: content_del',
      'ta\ndata: {"content": "split acr',
      'oss chunks"}\n\n',
    ]);

    const events = await collect(stream);

    expect(events).toEqual([{ type: "content_delta", content: "split across chunks" }]);
  });

  it("ignores an unknown event type instead of throwing", async () => {
    const stream = sseStream([
      'event: unknown_future_event\ndata: {"foo": "bar"}\n\n',
      'event: content_delta\ndata: {"content": "still works"}\n\n',
    ]);

    const events = await collect(stream);

    expect(events).toEqual([{ type: "content_delta", content: "still works" }]);
  });
});
