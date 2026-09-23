import { useEffect } from "react";
import { act, render, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatStreamEvent } from "@/features/chat/api/stream-chat-events";
import type { ConversationReplay } from "@/features/chat/api/get-conversation-messages";
import { sampleTeam } from "@/features/chat/sample-data/team";
import type { ChatMessage } from "@/features/chat/types";
import { clearInFlightTurns } from "@/features/chat/in-flight-turn";

const sendMessageMock = vi.fn();
vi.mock("@/features/chat/api/send-message", () => ({
  sendMessage: (...args: unknown[]) => sendMessageMock(...args),
}));

const getConversationMessagesMock = vi.fn();
vi.mock("@/features/chat/api/get-conversation-messages", () => ({
  getConversationMessages: (...args: unknown[]) => getConversationMessagesMock(...args),
}));

const watchConversationMock = vi.fn();
vi.mock("@/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
  return {
    ...actual,
    watchConversation: (...args: unknown[]) => watchConversationMock(...args),
  };
});

// Import after the mocks above so the hook picks them up.
const { useChatThread } = await import("@/features/chat/hooks/use-chat-thread");

/** Turns a list of events into the async generator `sendMessage` normally returns. */
function eventStream(events: ChatStreamEvent[]) {
  return (async function* () {
    for (const event of events) {
      yield event;
    }
  })();
}

/** A no-turn-in-progress watch response -- the default so existing tests,
 * none of which exercise reattachment, see the same "nothing to reattach
 * to" behavior as before `watchConversation` existed. */
function noTurnInProgress(): Response {
  return new Response(null, { status: 204 });
}

/** A live watch response streaming the given SSE frames. */
function watchStreamResponse(frames: string[]): Response {
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

function lastMessage(messages: ChatMessage[]): ChatMessage {
  return messages[messages.length - 1];
}

/**
 * Replicates the real `HomeShell` / `ConversationHydrator` composition: a
 * child component's effect calls `hydrate` before the parent's own
 * history-load effect runs, since React commits descendant effects before
 * the ancestor's for the same commit. A plain `renderHook()` call cannot
 * reproduce that ordering because there is no child in the tree.
 */
function ChildHydrator({
  hydrate,
  conversationId,
  replay,
}: {
  hydrate: (id: string, replay: ConversationReplay) => void;
  conversationId: string;
  replay: ConversationReplay;
}) {
  useEffect(() => {
    hydrate(conversationId, replay);
  }, [hydrate, conversationId, replay]);
  return null;
}

function HookProbe({
  urlConversationId,
  hydrateOnMount,
  onResult,
}: {
  urlConversationId: string | null;
  hydrateOnMount?: { conversationId: string; replay: ConversationReplay };
  onResult: (chat: ReturnType<typeof useChatThread>) => void;
}) {
  const chat = useChatThread({ urlConversationId });
  onResult(chat);
  return hydrateOnMount ? (
    <ChildHydrator
      hydrate={chat.hydrate}
      conversationId={hydrateOnMount.conversationId}
      replay={hydrateOnMount.replay}
    />
  ) : null;
}

describe("useChatThread", () => {
  beforeEach(() => {
    sendMessageMock.mockReset();
    getConversationMessagesMock.mockReset();
    getConversationMessagesMock.mockResolvedValue({
      conversationId: "550e8400-e29b-41d4-a716-446655440000",
      title: "New chat",
      messages: [],
    });
    watchConversationMock.mockReset();
    watchConversationMock.mockResolvedValue(noTurnInProgress());
    clearInFlightTurns();
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

  it("mints a conversation UUID and reports it before the first send", async () => {
    const onConversationCreated = vi.fn();
    sendMessageMock.mockReturnValue(
      eventStream([{ type: "error", detail: "The chat assistant is temporarily unavailable" }]),
    );

    const { result } = renderHook(() =>
      useChatThread({ urlConversationId: null, onConversationCreated }),
    );

    await act(async () => {
      await result.current.submit("Hi there");
    });

    expect(onConversationCreated).toHaveBeenCalledTimes(1);
    const mintedId = onConversationCreated.mock.calls[0][0] as string;
    expect(mintedId).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );
    expect(sendMessageMock).toHaveBeenCalledWith(mintedId, "Hi there");
  });

  it("reuses the URL conversation id and does not mint another", async () => {
    const urlId = "550e8400-e29b-41d4-a716-446655440000";
    const onConversationCreated = vi.fn();
    sendMessageMock.mockReturnValue(
      eventStream([{ type: "error", detail: "The chat assistant is temporarily unavailable" }]),
    );

    const { result } = renderHook(() =>
      useChatThread({ urlConversationId: urlId, onConversationCreated }),
    );

    await act(async () => {
      await result.current.submit("Follow up");
    });

    expect(onConversationCreated).not.toHaveBeenCalled();
    expect(sendMessageMock).toHaveBeenCalledWith(urlId, "Follow up");
  });

  it("does not let an abandoned turn's finally clear isSending for the conversation switched to", async () => {
    const conversationA = "550e8400-e29b-41d4-a716-446655440000";
    const conversationB = "660e8400-e29b-41d4-a716-446655440001";

    let releaseA: (() => void) | undefined;
    const gateA = new Promise<void>((resolve) => {
      releaseA = resolve;
    });
    sendMessageMock.mockImplementationOnce(async function* (
      _id: string,
      _text: string,
      signal: AbortSignal,
    ) {
      await gateA;
      if (signal.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      yield { type: "content_delta", content: "late, abandoned reply" } as ChatStreamEvent;
    });
    sendMessageMock.mockImplementationOnce(async function* () {
      yield { type: "content_delta", content: "B's own reply" } as ChatStreamEvent;
    });

    const { result, rerender } = renderHook(
      ({ urlConversationId }: { urlConversationId: string | null }) =>
        useChatThread({ urlConversationId }),
      { initialProps: { urlConversationId: conversationA } },
    );

    // Start a turn in A; it hangs on `gateA`, so it's still in flight.
    act(() => {
      void result.current.submit("Hello A");
    });
    expect(result.current.isSending).toBe(true);

    // Switch to B before A's stream resolves -- this aborts A's controller.
    rerender({ urlConversationId: conversationB });
    expect(result.current.isSending).toBe(false);

    // Start B's own turn, genuinely in flight.
    await act(async () => {
      await result.current.submit("Hello B");
    });
    expect(result.current.isSending).toBe(false); // B's stream already resolved above

    // Start a second, still-hanging B turn so isSending is true for B...
    let releaseB: (() => void) | undefined;
    const gateB = new Promise<void>((resolve) => {
      releaseB = resolve;
    });
    sendMessageMock.mockImplementationOnce(async function* () {
      await gateB;
      yield { type: "content_delta", content: "B's second reply" } as ChatStreamEvent;
    });
    act(() => {
      void result.current.submit("Hello again B");
    });
    expect(result.current.isSending).toBe(true);

    // ...then let A's long-abandoned turn finally resolve (or throw Aborted).
    await act(async () => {
      releaseA?.();
      await gateA;
    });

    // A's late finish must not have touched isSending for B's still-live turn.
    expect(result.current.isSending).toBe(true);

    await act(async () => {
      releaseB?.();
      await gateB;
    });
    expect(result.current.isSending).toBe(false);
  });

  it("clears the thread when the URL conversation id is removed", async () => {
    sendMessageMock.mockReturnValue(
      eventStream([
        {
          type: "message_done",
          conversation_id: "550e8400-e29b-41d4-a716-446655440000",
          parts: [{ type: "text", content: "Hello world" }],
          model: null,
        },
      ]),
    );

    const { result, rerender } = renderHook(
      ({ urlConversationId }: { urlConversationId: string | null }) =>
        useChatThread({ urlConversationId }),
      { initialProps: { urlConversationId: "550e8400-e29b-41d4-a716-446655440000" } },
    );

    await act(async () => {
      await result.current.submit("Hi there");
    });
    expect(result.current.messages).toHaveLength(2);

    rerender({ urlConversationId: null });
    expect(result.current.messages).toHaveLength(0);
  });

  it("replays stored messages when the URL already has a conversation id", async () => {
    const urlId = "550e8400-e29b-41d4-a716-446655440000";
    getConversationMessagesMock.mockResolvedValue({
      conversationId: urlId,
      title: "Argentina defence",
      messages: [
        {
          id: `${urlId}:0`,
          role: "user",
          parts: [{ type: "text", content: "How did Argentina do?" }],
        },
        {
          id: `${urlId}:1`,
          role: "assistant",
          parts: [{ type: "text", content: "They kept a clean sheet." }],
        },
      ],
    });

    const { result } = renderHook(() => useChatThread({ urlConversationId: urlId }));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    expect(result.current.messages[0]?.parts).toEqual([
      { type: "text", content: "How did Argentina do?" },
    ]);
    expect(getConversationMessagesMock).toHaveBeenCalledWith(urlId, expect.any(AbortSignal));
  });

  it("keeps the in-flight user message when the URL has not yet caught up", async () => {
    const onConversationCreated = vi.fn();
    sendMessageMock.mockReturnValue(
      eventStream([
        { type: "content_delta", content: "Hello" },
        {
          type: "message_done",
          conversation_id: "ignored",
          parts: [{ type: "text", content: "Hello" }],
          model: null,
        },
      ]),
    );

    const { result } = renderHook(() =>
      useChatThread({ urlConversationId: null, onConversationCreated }),
    );

    await act(async () => {
      await result.current.submit("Compare Messi vs Mbappé");
    });

    expect(onConversationCreated).toHaveBeenCalledOnce();
    expect(result.current.messages[0]?.parts).toEqual([
      { type: "text", content: "Compare Messi vs Mbappé" },
    ]);
    expect(result.current.messages[1]?.parts).toEqual([{ type: "text", content: "Hello" }]);
  });

  it("keeps the in-flight user message when the URL updates to the minted id", async () => {
    const onConversationCreated = vi.fn();
    sendMessageMock.mockReturnValue(
      eventStream([
        { type: "content_delta", content: "Hello" },
        {
          type: "message_done",
          conversation_id: "ignored",
          parts: [{ type: "text", content: "Hello" }],
          model: null,
        },
      ]),
    );

    const { result, rerender } = renderHook(
      ({ urlConversationId }: { urlConversationId: string | null }) =>
        useChatThread({ urlConversationId, onConversationCreated }),
      { initialProps: { urlConversationId: null } },
    );

    await act(async () => {
      await result.current.submit("Compare Messi vs Mbappé");
    });
    const mintedId = onConversationCreated.mock.calls[0][0] as string;
    expect(result.current.messages[0]?.parts).toEqual([
      { type: "text", content: "Compare Messi vs Mbappé" },
    ]);

    getConversationMessagesMock.mockResolvedValue({
      conversationId: mintedId,
      title: "New chat",
      messages: [],
    });
    rerender({ urlConversationId: mintedId });

    await waitFor(() => {
      expect(result.current.messages[0]?.parts).toEqual([
        { type: "text", content: "Compare Messi vs Mbappé" },
      ]);
    });
  });

  it("restores the in-flight turn after the hook remounts on the minted URL", async () => {
    const onConversationCreated = vi.fn();
    sendMessageMock.mockReturnValue(
      eventStream([{ type: "error", detail: "The chat assistant is temporarily unavailable" }]),
    );

    const first = renderHook(() =>
      useChatThread({ urlConversationId: null, onConversationCreated }),
    );
    await act(async () => {
      await first.result.current.submit("Compare Messi vs Mbappé");
    });
    const mintedId = onConversationCreated.mock.calls[0][0] as string;
    first.unmount();

    getConversationMessagesMock.mockResolvedValue({
      conversationId: mintedId,
      title: "New chat",
      messages: [],
    });
    const second = renderHook(() => useChatThread({ urlConversationId: mintedId }));

    expect(second.result.current.messages[0]?.parts).toEqual([
      { type: "text", content: "Compare Messi vs Mbappé" },
    ]);
  });

  it("hydrate populates messages/conversationId and skips the client-side history fetch", async () => {
    const urlId = "550e8400-e29b-41d4-a716-446655440000";
    let latest: ReturnType<typeof useChatThread> | undefined;

    render(
      <HookProbe
        urlConversationId={urlId}
        hydrateOnMount={{
          conversationId: urlId,
          replay: {
            conversationId: urlId,
            title: "Argentina defence",
            messages: [
              {
                id: `${urlId}:0`,
                role: "user",
                parts: [{ type: "text", content: "How did Argentina do?" }],
              },
              {
                id: `${urlId}:1`,
                role: "assistant",
                parts: [{ type: "text", content: "They kept a clean sheet." }],
              },
            ],
          },
        }}
        onResult={(chat) => {
          latest = chat;
        }}
      />,
    );

    await waitFor(() => {
      expect(latest?.isLoadingHistory).toBe(false);
    });
    expect(latest?.conversationId).toBe(urlId);
    expect(latest?.messages).toHaveLength(2);
    expect(latest?.messages[0]?.parts).toEqual([
      { type: "text", content: "How did Argentina do?" },
    ]);
    expect(getConversationMessagesMock).not.toHaveBeenCalled();
  });

  it("hydrate ignores a stale call for a conversation the URL already navigated away from", async () => {
    const urlId = "550e8400-e29b-41d4-a716-446655440000";
    const staleId = "660e8400-e29b-41d4-a716-446655440001";
    const { result } = renderHook(() => useChatThread({ urlConversationId: urlId }));

    act(() => {
      result.current.hydrate(staleId, {
        conversationId: staleId,
        title: "Stale",
        messages: [{ id: `${staleId}:0`, role: "user", parts: [{ type: "text", content: "old" }] }],
      });
    });

    expect(result.current.conversationId).toBe(urlId);
    expect(result.current.messages).toHaveLength(0);
  });

  it("reattaches to a background job still generating on load, appending a live assistant message after history", async () => {
    const urlId = "550e8400-e29b-41d4-a716-446655440000";
    getConversationMessagesMock.mockResolvedValue({
      conversationId: urlId,
      title: "Argentina defence",
      messages: [
        {
          id: `${urlId}:0`,
          role: "user",
          parts: [{ type: "text", content: "How did Argentina do?" }],
        },
      ],
    });
    watchConversationMock.mockResolvedValue(
      watchStreamResponse([
        'event: content_delta\ndata: {"content": "They kept a clean sheet."}\n\n',
        'event: message_done\ndata: {"conversation_id": "' +
          urlId +
          '", "parts": [{"type": "text", "content": "They kept a clean sheet."}], "model": null}\n\n',
      ]),
    );

    const { result } = renderHook(() => useChatThread({ urlConversationId: urlId }));

    await waitFor(() => {
      expect(result.current.isLoadingHistory).toBe(false);
      expect(result.current.isSending).toBe(false);
    });
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]?.role).toBe("user");
    const assistantMessage = lastMessage(result.current.messages);
    expect(assistantMessage.role).toBe("assistant");
    expect(assistantMessage.parts).toEqual([
      { type: "text", content: "They kept a clean sheet." },
    ]);
    expect(assistantMessage.isStreaming).toBe(false);
  });

  it("does not let a late, stale hydrate() clobber an already-reattached live reply", async () => {
    // `ConversationHydrator` mounts behind a Suspense boundary and its
    // `hydrate()` call can land *after* the client's own reattach effect
    // already appended and finished streaming the live reply -- `hydrate`
    // must defer to that, not overwrite it with SSR's now-stale snapshot
    // (fetched before the turn finished, so it only has the question).
    const urlId = "550e8400-e29b-41d4-a716-446655440000";
    getConversationMessagesMock.mockResolvedValue({
      conversationId: urlId,
      title: "Argentina defence",
      messages: [
        {
          id: `${urlId}:0`,
          role: "user",
          parts: [{ type: "text", content: "How did Argentina do?" }],
        },
      ],
    });
    watchConversationMock.mockResolvedValue(
      watchStreamResponse([
        'event: content_delta\ndata: {"content": "They kept a clean sheet."}\n\n',
        'event: message_done\ndata: {"conversation_id": "' +
          urlId +
          '", "parts": [{"type": "text", "content": "They kept a clean sheet."}], "model": null}\n\n',
      ]),
    );

    const { result } = renderHook(() => useChatThread({ urlConversationId: urlId }));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.isSending).toBe(false);
    });

    act(() => {
      result.current.hydrate(urlId, {
        conversationId: urlId,
        title: "Argentina defence",
        messages: [
          {
            id: `${urlId}:0`,
            role: "user",
            parts: [{ type: "text", content: "How did Argentina do?" }],
          },
        ],
      });
    });

    expect(result.current.messages).toHaveLength(2);
    const assistantMessage = lastMessage(result.current.messages);
    expect(assistantMessage.role).toBe("assistant");
    expect(assistantMessage.parts).toEqual([
      { type: "text", content: "They kept a clean sheet." },
    ]);
  });

  it("does not reattach when watch reports nothing in progress (the default, no-turn case)", async () => {
    const urlId = "550e8400-e29b-41d4-a716-446655440000";
    getConversationMessagesMock.mockResolvedValue({
      conversationId: urlId,
      title: "Argentina defence",
      messages: [
        { id: `${urlId}:0`, role: "user", parts: [{ type: "text", content: "How did Argentina do?" }] },
        { id: `${urlId}:1`, role: "assistant", parts: [{ type: "text", content: "They won." }] },
      ],
    });

    const { result } = renderHook(() => useChatThread({ urlConversationId: urlId }));

    await waitFor(() => {
      expect(result.current.isLoadingHistory).toBe(false);
    });
    expect(result.current.isSending).toBe(false);
    expect(result.current.messages).toHaveLength(2);
  });
});
