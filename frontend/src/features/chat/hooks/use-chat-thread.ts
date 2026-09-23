"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, watchConversation } from "@/lib/api/client";
import {
  getConversationMessages,
  type ConversationReplay,
} from "@/features/chat/api/get-conversation-messages";
import { sendMessage } from "@/features/chat/api/send-message";
import {
  streamChatEvents,
  type ChatStreamEvent,
} from "@/features/chat/api/stream-chat-events";
import { newConversationId } from "@/features/chat/conversation-id";
import {
  forgetInFlightTurn,
  readInFlightTurn,
  rememberInFlightTurn,
} from "@/features/chat/in-flight-turn";
import { parseMessageParts } from "@/features/chat/parse-message-parts";
import { messagePartSchema } from "@/features/chat/schemas/message-part.schema";
import type { ChatMessage, EntityRef, MessagePart } from "@/features/chat/types";

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `msg_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function widgetPartRefAndData(part: MessagePart): [EntityRef, unknown] | null {
  switch (part.type) {
    case "team_widget":
      return [{ type: "team", id: part.data.id }, part.data];
    case "match_widget":
      return [{ type: "match", id: part.data.id }, part.data];
    case "player_widget":
      return [{ type: "player", id: part.data.id }, part.data];
    case "compare_widget":
      return [{ type: "compare", id: part.data.id }, part.data];
    default:
      return null;
  }
}

/** Appends a content delta onto the last text part, or starts a new one. */
function appendTextDelta(parts: MessagePart[], delta: string): MessagePart[] {
  const last = parts[parts.length - 1];
  if (last?.type === "text") {
    return [...parts.slice(0, -1), { type: "text", content: last.content + delta }];
  }
  return [...parts, { type: "text", content: delta }];
}

/**
 * Applies one SSE event onto the in-progress assistant message via
 * `updateAssistant`. Shared by a live `submit()` turn and a reattached one
 * (`watchConversation` picking a background job's stream back up) -- both
 * are just "drive this event source into this one message" once the send
 * step (if any) is already done.
 */
function applyStreamEvent(
  event: ChatStreamEvent,
  updateAssistant: (updater: (message: ChatMessage) => ChatMessage) => void,
): void {
  switch (event.type) {
    case "reasoning_delta":
      updateAssistant((message) => ({
        ...message,
        reasoning: (message.reasoning ?? "") + event.content,
      }));
      break;
    case "content_delta":
      updateAssistant((message) => ({
        ...message,
        parts: appendTextDelta(message.parts, event.content),
      }));
      break;
    case "tool_call":
      updateAssistant((message) => ({ ...message, activeToolName: event.name }));
      break;
    case "widget_ready": {
      const result = messagePartSchema.safeParse(event.part);
      if (result.success) {
        updateAssistant((message) => ({
          ...message,
          parts: [...message.parts, result.data],
        }));
      }
      break;
    }
    case "cap_reached":
      // `content` is the full best-effort partial text (not a delta);
      // the clarification is rendered as a distinct note, not folded
      // into the same text.
      updateAssistant((message) => ({
        ...message,
        parts: [{ type: "text", content: event.content }],
        clarification: event.clarification,
        activeToolName: undefined,
      }));
      break;
    case "message_done":
      updateAssistant((message) => ({
        ...message,
        // On a cap-trip, message_done's text is the same partial
        // content with the clarification appended -- keep the
        // already-rendered cap_reached text instead of duplicating
        // the clarification into the visible content.
        parts: message.clarification ? message.parts : parseMessageParts(event.parts),
        isStreaming: false,
        activeToolName: undefined,
      }));
      break;
    case "error":
      updateAssistant((message) => ({
        ...message,
        error: event.detail,
        isStreaming: false,
        activeToolName: undefined,
      }));
      break;
  }
}

export type UseChatThreadArgs = {
  urlConversationId?: string | null;
  onConversationCreated?: (id: string) => void;
};

/**
 * Owns the message thread and the conversation id, and calls the chat API.
 * Also derives an entity registry (id -> widget data) from every widget
 * part seen so far, so the side panel can resolve an `EntityRef` without a
 * separate fetch -- the data already arrived inline with the message.
 *
 * The conversation UUID is minted on the client before the first send and
 * pushed into the URL by the caller (`onConversationCreated`). The URL is
 * the identity thereafter; a later `message_done.conversation_id` is ignored.
 */
export function useChatThread({
  urlConversationId = null,
  onConversationCreated,
}: UseChatThreadArgs = {}) {
  const restored = urlConversationId ? readInFlightTurn(urlConversationId) : undefined;
  const [messages, setMessagesState] = useState<ChatMessage[]>(() => restored ?? []);
  const [conversationId, setConversationId] = useState<string | null>(urlConversationId);
  const [isSending, setIsSending] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(
    Boolean(urlConversationId) && !restored?.length,
  );
  const conversationIdRef = useRef<string | null>(urlConversationId);
  conversationIdRef.current = conversationId;
  const onConversationCreatedRef = useRef(onConversationCreated);
  onConversationCreatedRef.current = onConversationCreated;
  const previousUrlIdRef = useRef(urlConversationId);
  const skipHistoryLoadRef = useRef(Boolean(restored?.length));
  const historyRequestIdRef = useRef(0);
  const hydratedConversationIdRef = useRef<string | null>(null);

  const setMessages = useCallback(
    (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
      setMessagesState((prev) => {
        const next = typeof updater === "function" ? updater(prev) : updater;
        const id = conversationIdRef.current;
        if (id && next.length > 0) {
          rememberInFlightTurn(id, next);
        }
        return next;
      });
    },
    [],
  );

  /**
   * Drives one already-open event source (a fresh `sendMessage` stream, or
   * a reattached `watchConversation` one) into the given assistant message
   * until it terminates, then clears `isSending` -- but only if the viewed
   * conversation hasn't moved on since this turn started (see `submit`'s
   * original comment on why an abandoned turn must never touch a different
   * conversation's state).
   */
  const runTurn = useCallback(
    async (events: AsyncGenerator<ChatStreamEvent>, assistantId: string, activeConversationId: string) => {
      const updateAssistant = (updater: (message: ChatMessage) => ChatMessage) => {
        setMessages((prev) =>
          prev.map((message) => (message.id === assistantId ? updater(message) : message)),
        );
      };

      try {
        for await (const event of events) {
          applyStreamEvent(event, updateAssistant);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          // We never abort this fetch ourselves (see the conversation-switch
          // effect's comment) -- this only fires for a genuinely external
          // cancellation, e.g. the browser tab closing. Not a failure worth
          // showing the user.
        } else {
          const detail =
            error instanceof ApiError
              ? error.message
              : "The chat assistant is temporarily unavailable";
          updateAssistant((message) => ({
            ...message,
            error: detail,
            isStreaming: false,
            activeToolName: undefined,
          }));
        }
      } finally {
        if (conversationIdRef.current === activeConversationId) {
          setIsSending(false);
        }
      }
    },
    [setMessages],
  );

  useEffect(() => {
    const previousUrlId = previousUrlIdRef.current;
    if (urlConversationId === previousUrlId) {
      return;
    }
    previousUrlIdRef.current = urlConversationId;
    // Deliberately NOT aborting the in-flight stream here. Generation now
    // runs as a background job (`generate_chat_reply_task`) fully decoupled
    // from any HTTP connection -- aborting the `watch` fetch only stops
    // this client from observing it, it can no longer kill the turn or lose
    // the message server-side. Not aborting is still the simpler choice:
    // `submit`'s `finally` guard (conversationIdRef check) already stops a
    // stale watch from touching isSending/messages for whatever
    // conversation is active by the time it resolves, so there is nothing
    // to gain from tearing down the old connection early.
    //
    // `isSending` is reset here regardless, since that guard means the old
    // turn's own `finally` will not clear it once the conversation has
    // moved on -- otherwise a turn still in flight would leave `isSending`
    // stuck `true` for whatever's viewed next.
    setIsSending(false);

    if (urlConversationId === null) {
      if (conversationIdRef.current) {
        forgetInFlightTurn(conversationIdRef.current);
      }
      setConversationId(null);
      setMessages([]);
      return;
    }

    setConversationId(urlConversationId);
    if (conversationIdRef.current !== urlConversationId) {
      setMessages(readInFlightTurn(urlConversationId) ?? []);
    }
  }, [setMessages, urlConversationId]);

  useEffect(() => {
    if (!urlConversationId) {
      setIsLoadingHistory(false);
      return;
    }
    if (hydratedConversationIdRef.current === urlConversationId) {
      // SSR already delivered this exact conversation's data via `hydrate`.
      setIsLoadingHistory(false);
      return;
    }
    if (skipHistoryLoadRef.current) {
      const skipForMintedTurn = conversationIdRef.current === urlConversationId;
      skipHistoryLoadRef.current = false;
      if (skipForMintedTurn) {
        setIsLoadingHistory(false);
        return;
      }
    }
    if ((readInFlightTurn(urlConversationId)?.length ?? 0) > 0) {
      setIsLoadingHistory(false);
      return;
    }

    const requestId = ++historyRequestIdRef.current;
    setIsLoadingHistory(true);

    // React (Strict Mode, dev only) double-invokes this effect synchronously
    // -- run, cleanup, run again -- to surface exactly this class of bug:
    // without a cleanup that cancels the first invocation's in-flight
    // fetches, both invocations would independently reach `watchConversation`
    // and open two live connections to the same background job, each
    // driving its own draft assistant message. `historyRequestIdRef` alone
    // catches this for the two *fetches* (the loser's `.then` bails), but
    // not fast enough to stop the loser's requests from firing at all, and
    // not the two watch connections both actually opening. The abort
    // controller below is the real fix -- the loser's cleanup cancels it
    // before its fetches even land, so only the winner ever calls
    // `watchConversation`.
    const controller = new AbortController();
    let handedOffToRunTurn = false;

    void (async () => {
      let replay: ConversationReplay;
      try {
        replay = await getConversationMessages(urlConversationId, controller.signal);
      } catch {
        // Keep whatever is already on screen (an in-flight first turn).
        // Also the expected path when this invocation lost the Strict Mode
        // race and its cleanup aborted the fetch above.
        if (requestId === historyRequestIdRef.current) {
          setIsLoadingHistory(false);
        }
        return;
      }
      if (requestId !== historyRequestIdRef.current) {
        return;
      }

      // Reattachment: a background job may still be generating this
      // conversation's reply (e.g. the tab was closed and reopened, or
      // this is a second tab). Best-effort -- a failed probe just falls
      // back to the static replay, same as a genuine 204. Only tried on
      // this client-side path, not the SSR `hydrate` one (`hydrate`
      // returns early above); a first server-rendered load of a
      // generating conversation shows the static reply-in-progress
      // history until the user navigates away and back.
      let watchResponse: Response | null = null;
      try {
        watchResponse = await watchConversation(urlConversationId, controller.signal);
      } catch {
        watchResponse = null;
      }
      if (requestId !== historyRequestIdRef.current) {
        return;
      }

      if (!watchResponse || watchResponse.status === 204 || !watchResponse.body) {
        setMessages((prev) => (prev.length > 0 ? prev : replay.messages));
        setConversationId(urlConversationId);
        setIsLoadingHistory(false);
        return;
      }

      const assistantId = makeId();
      const draftAssistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        parts: [],
        reasoning: "",
        isStreaming: true,
      };
      setMessages((prev) => {
        // Not a plain "already non-empty, skip" guard: `hydrate` (SSR,
        // behind a Suspense boundary) races this same effect and can land
        // either before or after it. If `hydrate` already won, `prev` is
        // its `replay.messages` -- same content this call already fetched,
        // still ending in the unanswered user message -- and this must
        // still append the draft on top of it, not defer to it. Only skip
        // when the last message is already an assistant reply (a genuine
        // second run appending on top of itself, e.g. Strict Mode without
        // the abort actually landing in time).
        const last = prev[prev.length - 1];
        if (last && last.role !== "user") {
          return prev;
        }
        return [...replay.messages, draftAssistantMessage];
      });
      setConversationId(urlConversationId);
      setIsLoadingHistory(false);
      setIsSending(true);
      // Once handed off, `runTurn` owns this stream -- the cleanup below
      // must not abort it. Consuming an in-progress background job's
      // stream is exactly the case the conversation-switch effect's own
      // comment already covers: never torn down early, generation
      // continues (and here, is already complete) regardless of who is
      // watching.
      handedOffToRunTurn = true;
      void runTurn(streamChatEvents(watchResponse.body), assistantId, urlConversationId);
    })();

    return () => {
      if (!handedOffToRunTurn) {
        controller.abort();
      }
    };
  }, [runTurn, setMessages, urlConversationId]);

  const entityRegistry = useMemo(() => {
    const registry = new Map<string, unknown>();
    for (const message of messages) {
      for (const part of message.parts) {
        const entry = widgetPartRefAndData(part);
        if (entry) {
          const [ref, data] = entry;
          registry.set(`${ref.type}:${ref.id}`, data);
        }
      }
    }
    return registry;
  }, [messages]);

  const resolveEntity = useCallback(
    (ref: EntityRef) => entityRegistry.get(`${ref.type}:${ref.id}`),
    [entityRegistry],
  );

  const submit = useCallback(
    async (text: string) => {
      const userMessage: ChatMessage = {
        id: makeId(),
        role: "user",
        parts: [{ type: "text", content: text }],
      };
      const assistantId = makeId();
      const draftAssistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        parts: [],
        reasoning: "",
        isStreaming: true,
      };

      let activeConversationId = conversationIdRef.current;
      const didMintConversation = activeConversationId === null;
      if (activeConversationId === null) {
        activeConversationId = newConversationId();
        conversationIdRef.current = activeConversationId;
        setConversationId(activeConversationId);
        skipHistoryLoadRef.current = true;
      }

      setMessages((prev) => [...prev, userMessage, draftAssistantMessage]);
      if (didMintConversation) {
        onConversationCreatedRef.current?.(activeConversationId);
      }
      setIsSending(true);
      historyRequestIdRef.current += 1;

      await runTurn(sendMessage(activeConversationId, text), assistantId, activeConversationId);
    },
    [runTurn, setMessages],
  );

  const hydrate = useCallback(
    (id: string, replay: ConversationReplay) => {
      if (id !== urlConversationId) return; // stale hydration call (navigated away already)
      hydratedConversationIdRef.current = id;
      setConversationId(id);
      // `prev.length > 0 ? prev : replay.messages`, not an unconditional
      // overwrite -- `ConversationHydrator` mounts behind a Suspense
      // boundary, so this can fire well after the client's own reattach
      // effect already appended a live draft assistant message for this
      // exact conversation (see that effect's comment). Overwriting
      // unconditionally here would silently replace that draft with SSR's
      // now-stale snapshot (fetched before the turn finished) and orphan
      // every subsequent stream event -- they'd keep targeting an
      // assistant id no longer present in the array.
      setMessages((prev) => (prev.length > 0 ? prev : replay.messages));
      setIsLoadingHistory(false);
    },
    [urlConversationId, setMessages],
  );

  const reset = useCallback(() => {
    // Does not abort an in-flight turn -- see the conversation-switch
    // effect's comment: generation is a background job, so there is
    // nothing to gain from tearing down the watch connection early.
    if (conversationIdRef.current) {
      forgetInFlightTurn(conversationIdRef.current);
    }
    setMessagesState([]);
    setConversationId(null);
    conversationIdRef.current = null;
    setIsSending(false);
  }, []);

  return {
    messages,
    conversationId,
    isSending,
    isLoadingHistory,
    submit,
    reset,
    resolveEntity,
    hydrate,
  };
}
