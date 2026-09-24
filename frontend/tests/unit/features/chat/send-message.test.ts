import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";

const sendChatMessageMock = vi.fn();
const watchConversationMock = vi.fn();
vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    sendChatMessage: (...args: unknown[]) => sendChatMessageMock(...args),
    watchConversation: (...args: unknown[]) => watchConversationMock(...args),
  };
});

const { sendMessage } = await import("@/features/chat/api/send-message");

function sseResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

async function collect(conversationId: string, message: string) {
  const events = [];
  for await (const event of sendMessage(conversationId, message)) {
    events.push(event);
  }
  return events;
}

describe("sendMessage", () => {
  beforeEach(() => {
    sendChatMessageMock.mockReset();
    watchConversationMock.mockReset();
  });

  it("acks the send, then streams events from the watch response", async () => {
    sendChatMessageMock.mockResolvedValue({
      conversationId: "conv-1",
      title: "A chat",
      streamCursor: "10-0",
    });
    watchConversationMock.mockResolvedValue(
      sseResponse([
        'event: content_delta\ndata: {"content": "Hi"}\n\n',
        'event: message_done\ndata: {"conversation_id": "conv-1", "parts": [{"type": "text", "content": "Hi"}], "model": null}\n\n',
      ]),
    );

    const events = await collect("conv-1", "Hello");

    expect(sendChatMessageMock).toHaveBeenCalledWith(
      { conversationId: "conv-1", message: "Hello" },
      undefined,
    );
    expect(watchConversationMock).toHaveBeenCalledWith("conv-1", undefined, "10-0");
    expect(events).toEqual([
      { type: "content_delta", content: "Hi" },
      {
        type: "message_done",
        conversation_id: "conv-1",
        parts: [{ type: "text", content: "Hi" }],
        model: null,
      },
    ]);
  });

  it("throws without ever watching when the send itself fails", async () => {
    sendChatMessageMock.mockRejectedValue(new ApiError("A reply is already in progress", 409));

    await expect(collect("conv-1", "Hello")).rejects.toThrow("A reply is already in progress");
    expect(watchConversationMock).not.toHaveBeenCalled();
  });

  it("resumes after the last frame id when the watch body ends before a terminal event", async () => {
    sendChatMessageMock.mockResolvedValue({
      conversationId: "conv-1",
      title: "A chat",
      streamCursor: "10-0",
    });
    watchConversationMock
      .mockResolvedValueOnce(
        sseResponse(['id: 11-0\nevent: content_delta\ndata: {"content": "Hi"}\n\n']),
      )
      .mockResolvedValueOnce(
        sseResponse([
          'id: 12-0\nevent: message_done\ndata: {"conversation_id": "conv-1", "parts": [{"type": "text", "content": "Hi"}], "model": null}\n\n',
        ]),
      );

    const events = await collect("conv-1", "Hello");

    expect(watchConversationMock).toHaveBeenNthCalledWith(1, "conv-1", undefined, "10-0");
    expect(watchConversationMock).toHaveBeenNthCalledWith(2, "conv-1", undefined, "11-0");
    expect(events.map((event) => event.type)).toEqual(["content_delta", "message_done"]);
  });

  it("throws when watch returns 204 (nothing in progress right after a fresh send)", async () => {
    sendChatMessageMock.mockResolvedValue({
      conversationId: "conv-1",
      title: "A chat",
      streamCursor: "10-0",
    });
    watchConversationMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(collect("conv-1", "Hello")).rejects.toThrow(ApiError);
  });
});
