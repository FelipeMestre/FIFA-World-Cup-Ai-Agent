"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  getConversationMessages,
  type ConversationReplay,
} from "@/features/chat/api/get-conversation-messages";
import { sendMessage } from "@/features/chat/api/send-message";
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
  /**
   * The in-flight turn's stream, if any. Aborted whenever the viewed
   * conversation changes (switch or reset) so an abandoned turn can't touch
   * `isSending`/messages for whatever conversation is now active -- see
   * `submit`'s `finally` guard below for why aborting the fetch alone isn't
   * enough (the abort's own catch/finally still run and need gating too).
   */
  const activeStreamControllerRef = useRef<AbortController | null>(null);

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

  useEffect(() => {
    const previousUrlId = previousUrlIdRef.current;
    if (urlConversationId === previousUrlId) {
      return;
    }
    previousUrlIdRef.current = urlConversationId;
    // Leaving whatever conversation was active -- stop its stream, if any,
    // so it can't keep writing into what's about to become a different
    // conversation's state. `isSending` is reset here too: the `finally` in
    // `submit` deliberately will not clear it once the conversation has
    // moved on (see its guard), so this is the only place that does for a
    // switch -- otherwise a turn abandoned mid-stream would leave
    // `isSending` stuck `true` forever for whatever's viewed next.
    activeStreamControllerRef.current?.abort();
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

    void getConversationMessages(urlConversationId)
      .then((replay) => {
        if (requestId !== historyRequestIdRef.current) {
          return;
        }
        setMessages((prev) => (prev.length > 0 ? prev : replay.messages));
        setConversationId(urlConversationId);
      })
      .catch(() => {
        // Keep whatever is already on screen (an in-flight first turn).
      })
      .finally(() => {
        if (requestId === historyRequestIdRef.current) {
          setIsLoadingHistory(false);
        }
      });
  }, [setMessages, urlConversationId]);

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
      if (didMintConversation) {
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

      // Defensive: a second submit while one is already in flight (shouldn't
      // happen -- the composer disables during isSending -- but this keeps
      // the invariant "at most one live stream per hook instance" true
      // regardless of how it's triggered.
      activeStreamControllerRef.current?.abort();
      const controller = new AbortController();
      activeStreamControllerRef.current = controller;

      const updateAssistant = (updater: (message: ChatMessage) => ChatMessage) => {
        setMessages((prev) =>
          prev.map((message) => (message.id === assistantId ? updater(message) : message)),
        );
      };

      try {
        for await (const event of sendMessage(activeConversationId, text, controller.signal)) {
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
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          // Deliberately cancelled (conversation switch or reset) -- not a
          // real failure, nothing to show the user.
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
        // Only clear isSending for the conversation this turn actually
        // belongs to -- an abandoned turn finishing late (aborted or not)
        // must never flip isSending for whatever conversation is now
        // active. This is the fix for the cross-conversation leak: prior to
        // this guard, `finally` ran unconditionally.
        if (conversationIdRef.current === activeConversationId) {
          setIsSending(false);
        }
        if (activeStreamControllerRef.current === controller) {
          activeStreamControllerRef.current = null;
        }
      }
    },
    [conversationId],
  );

  const hydrate = useCallback(
    (id: string, replay: ConversationReplay) => {
      if (id !== urlConversationId) return; // stale hydration call (navigated away already)
      hydratedConversationIdRef.current = id;
      setConversationId(id);
      setMessages(replay.messages);
      setIsLoadingHistory(false);
    },
    [urlConversationId, setMessages],
  );

  const reset = useCallback(() => {
    activeStreamControllerRef.current?.abort();
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
