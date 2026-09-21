import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatStreamEvent } from "@/features/chat/api/stream-chat-events";
import { sampleTeam } from "@/features/chat/sample-data/team";
import type { ChatMessage } from "@/features/chat/types";

const sendMessageMock = vi.fn();
vi.mock("@/features/chat/api/send-message", () => ({
  sendMessage: (...args: unknown[]) => sendMessageMock(...args),
}));

// Import after the mock above so the hook picks it up.
const { useChatThread } = await import("@/features/chat/hooks/use-chat-thread");

/** Turns a list of events into the async generator `sendMessage` normally returns. */
function eventStream(events: ChatStreamEvent[]) {
  return (async function* () {
    for (const event of events) {
      yield event;
    }
  })();
}

function lastMessage(messages: ChatMessage[]): ChatMessage {
  return messages[messages.length - 1];
}

describe("useChatThread", () => {
  beforeEach(() => {
    sendMessageMock.mockReset();
  });

  it("incrementally builds the assistant message's content as content_delta events arrive", async () => {
    sendMessageMock.mockReturnValue(
      eventStream([
        { type: "reasoning_delta", content: "Thinking about it" },
        { type: "content_delta", content: "Hello" },
        { type: "content_delta", content: " world" },
        {
          type: "message_done",
          conversation_id: "conv-1",
          parts: [{ type: "text", content: "Hello world" }],
          model: "anthropic/claude-sonnet-4.5",
        },
      ]),
    );

    const { result } = renderHook(() => useChatThread());

    await act(async () => {
      await result.current.submit("Hi there");
    });

    await waitFor(() => {
      const assistantMessage = lastMessage(result.current.messages);
      expect(assistantMessage.role).toBe("assistant");
    });

    const assistantMessage = lastMessage(result.current.messages);

    expect(assistantMessage.parts).toEqual([{ type: "text", content: "Hello world" }]);
    expect(assistantMessage.reasoning).toBe("Thinking about it");
    expect(assistantMessage.isStreaming).toBe(false);
  });

  it("shows an active tool-call indicator while the loop dispatches a tool, then clears it", async () => {
    sendMessageMock.mockReturnValue(
      eventStream([
        { type: "tool_call", name: "get_current_utc_time" },
        { type: "content_delta", content: "It is currently 10am UTC." },
        {
          type: "message_done",
          conversation_id: "conv-1",
          parts: [{ type: "text", content: "It is currently 10am UTC." }],
          model: null,
        },
      ]),
    );

    const { result } = renderHook(() => useChatThread());

    await act(async () => {
      await result.current.submit("What time is it?");
    });

    const assistantMessage = lastMessage(result.current.messages);
    expect(assistantMessage.activeToolName).toBeUndefined();
  });

  it("renders the cap_reached clarification distinctly from the partial content, without duplicating it", async () => {
    sendMessageMock.mockReturnValue(
      eventStream([
        { type: "content_delta", content: "Based on what I found so far..." },
        {
          type: "cap_reached",
          content: "Based on what I found so far...",
          clarification: "Could you clarify what you are looking for?",
        },
        {
          type: "message_done",
          conversation_id: "conv-1",
          parts: [
            {
              type: "text",
              content:
                "Based on what I found so far... Could you clarify what you are looking for?",
            },
          ],
          model: null,
        },
      ]),
    );

    const { result } = renderHook(() => useChatThread());

    await act(async () => {
      await result.current.submit("Find something obscure");
    });

    const assistantMessage = lastMessage(result.current.messages);

    expect(assistantMessage.clarification).toBe("Could you clarify what you are looking for?");
    // The visible content stays the pre-cap partial text -- the clarification
    // is a separate field, not folded into `parts` a second time.
    expect(assistantMessage.parts).toEqual([
      { type: "text", content: "Based on what I found so far..." },
    ]);
    expect(assistantMessage.isStreaming).toBe(false);
  });

  it("renders a widget live, before message_done arrives, without duplicating it", async () => {
    sendMessageMock.mockReturnValue(
      eventStream([
        { type: "tool_call", name: "get_team_analysis" },
        { type: "widget_ready", part: { type: "team_widget", data: sampleTeam } },
        { type: "content_delta", content: "Here's how they did." },
        {
          type: "message_done",
          conversation_id: "conv-1",
          parts: [
            { type: "text", content: "Here's how they did." },
            { type: "team_widget", data: sampleTeam },
          ],
          model: "anthropic/claude-sonnet-4.5",
        },
      ]),
    );

    const { result } = renderHook(() => useChatThread());

    await act(async () => {
      await result.current.submit("How did Argentina do?");
    });

    const assistantMessage = lastMessage(result.current.messages);
    expect(assistantMessage.parts).toEqual([
      { type: "text", content: "Here's how they did." },
      { type: "team_widget", data: sampleTeam },
    ]);
  });

  it("drops a widget_ready part that fails the widget contract's schema, instead of crashing", async () => {
    sendMessageMock.mockReturnValue(
      eventStream([
        { type: "widget_ready", part: { type: "team_widget", data: { incomplete: true } } },
        { type: "content_delta", content: "Text still renders." },
        {
          type: "message_done",
          conversation_id: "conv-1",
          parts: [{ type: "text", content: "Text still renders." }],
          model: null,
        },
      ]),
    );

    const { result } = renderHook(() => useChatThread());

    await act(async () => {
      await result.current.submit("How did Argentina do?");
    });

    const assistantMessage = lastMessage(result.current.messages);
    expect(assistantMessage.parts).toEqual([{ type: "text", content: "Text still renders." }]);
  });

  it("surfaces an error event as the assistant message's error state", async () => {
    sendMessageMock.mockReturnValue(
      eventStream([{ type: "error", detail: "The chat assistant is temporarily unavailable" }]),
    );

    const { result } = renderHook(() => useChatThread());

    await act(async () => {
      await result.current.submit("Hello");
    });

    const assistantMessage = lastMessage(result.current.messages);
    expect(assistantMessage.error).toBe("The chat assistant is temporarily unavailable");
    expect(assistantMessage.isStreaming).toBe(false);
  });
});
