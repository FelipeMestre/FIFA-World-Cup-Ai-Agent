"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  applyLiveEvent,
  isTerminalLiveEvent,
  markLastAssistantErrored,
} from "@/features/chat/apply-live-event";
import {
  connectConversationEvents,
  type ConversationEvent,
  type EventsConnection,
} from "@/features/chat/api/conversation-events";
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
import type { ChatMessage, EntityRef, MessagePart } from "@/features/chat/types";
import { ApiError } from "@/lib/api/client";

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
    case "ranking_widget":
      return [{ type: "ranking", id: part.data.id }, part.data];
    default:
      return null;
  }
}

function mergeHistory(previous: ChatMessage[], replay: ChatMessage[]): ChatMessage[] {
  if (previous.length === 0) return replay;
  // Deltas can land before the history response. They only append assistant
  // messages, so the saved user text still has to be placed in front.
  if (previous.every((message) => message.role === "assistant")) {
    return [...replay, ...previous];
  }
  return previous;
}

export type UseChatThreadArgs = {
  urlConversationId?: string | null;
  onConversationCreated?: (id: string) => void;
};

/**
 * Owns the message thread and the conversation id. One SSE connection stays
 * open for the conversation on screen (`GET /conversations/{id}/events`);
 * every client attached to it applies the same `user_message` and reply
 * events. Sending is a separate POST (`sendMessage`) -- `EventSource`
 * reconnects and resumes (`Last-Event-ID`) natively, so there is no
 * client-side cursor/dedup tracking here the way the old WebSocket needed.
 *
 * The conversation UUID is minted on the client before the first send and
 * pushed into the URL by the caller (`onConversationCreated`).
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
  const eventsRef = useRef<EventsConnection | null>(null);
  const onLiveEventRef = useRef<(event: ConversationEvent) => void>(() => {});

  const setMessages = useCallback(
    (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
      setMessagesState((prev) => {
        const next = typeof updater === "function" ? updater(prev) : updater;
        const id = conversationIdRef.current;
        if (id && next.length > 0) rememberInFlightTurn(id, next);
        return next;
      });
    },
    [],
  );

  onLiveEventRef.current = (event) => {
    setMessages((prev) => applyLiveEvent(prev, event));
    if (isTerminalLiveEvent(event)) setIsSending(false);
    else if (event.type === "user_message") setIsSending(true);
  };

  const ensureEvents = useCallback((id: string) => {
    const current = eventsRef.current;
    if (current && current.conversationId === id) return current;
    current?.close();
    const connection = connectConversationEvents(id, (event) => {
      if (conversationIdRef.current !== id) return;
      onLiveEventRef.current(event);
    });
    eventsRef.current = connection;
    return connection;
  }, []);

  useEffect(() => {
    return () => {
      eventsRef.current?.close();
      eventsRef.current = null;
    };
  }, [urlConversationId]);

  useEffect(() => {
    const previousUrlId = previousUrlIdRef.current;
    if (urlConversationId === previousUrlId) return;
    previousUrlIdRef.current = urlConversationId;
    conversationIdRef.current = urlConversationId;
    setIsSending(false);

    if (urlConversationId === null) {
      if (previousUrlId) forgetInFlightTurn(previousUrlId);
      setConversationId(null);
      setMessages([]);
      return;
    }

    setConversationId(urlConversationId);
    if (previousUrlId !== urlConversationId) {
      setMessages(readInFlightTurn(urlConversationId) ?? []);
    }
  }, [setMessages, urlConversationId]);

  useEffect(() => {
    if (!urlConversationId) {
      setIsLoadingHistory(false);
      return;
    }
    if (hydratedConversationIdRef.current === urlConversationId) {
      setIsLoadingHistory(false);
      ensureEvents(urlConversationId);
      return;
    }
    if (skipHistoryLoadRef.current) {
      const skipForMintedTurn = conversationIdRef.current === urlConversationId;
      skipHistoryLoadRef.current = false;
      if (skipForMintedTurn) {
        setIsLoadingHistory(false);
        ensureEvents(urlConversationId);
        return;
      }
    }
    if ((readInFlightTurn(urlConversationId)?.length ?? 0) > 0) {
      setIsLoadingHistory(false);
      ensureEvents(urlConversationId);
      return;
    }

    const requestId = ++historyRequestIdRef.current;
    setIsLoadingHistory(true);
    const controller = new AbortController();

    void (async () => {
      let replay: ConversationReplay;
      try {
        replay = await getConversationMessages(urlConversationId, controller.signal);
      } catch {
        if (requestId === historyRequestIdRef.current) setIsLoadingHistory(false);
        return;
      }
      if (requestId !== historyRequestIdRef.current || controller.signal.aborted) return;
      setMessages((prev) => mergeHistory(prev, replay.messages));
      setConversationId(urlConversationId);
      setIsLoadingHistory(false);
      ensureEvents(urlConversationId);
    })();

    return () => controller.abort();
  }, [ensureEvents, setMessages, urlConversationId]);

  const entityRegistry = useMemo(() => {
    const registry = new Map<string, unknown>();
    for (const message of messages) {
      for (const part of message.parts) {
        const entry = widgetPartRefAndData(part);
        if (entry) registry.set(`${entry[0].type}:${entry[0].id}`, entry[1]);
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
      const draftAssistant: ChatMessage = {
        id: makeId(),
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

      setMessages((prev) => [...prev, userMessage, draftAssistant]);
      if (didMintConversation) onConversationCreatedRef.current?.(activeConversationId);
      setIsSending(true);
      historyRequestIdRef.current += 1;

      // For an existing conversation the row already exists (and the
      // connection is normally already open from the mount/history
      // effect), so opening it here too is a safe, idempotent no-op.
      // For a brand-new, client-minted conversation the row does not
      // exist until this send's own `start_turn` creates it -- opening
      // the SSE connection before that races the merged endpoint's
      // existence check and can 404 it *permanently*: unlike a dropped
      // connection, `EventSource` does not retry after a non-2xx initial
      // response, so this is deferred until the send has actually
      // succeeded, once the conversation is guaranteed to exist. The
      // backend's own resume-from-reservation-cursor behavior still
      // replays the `user_message` entry this send just published, so
      // nothing is missed by opening it slightly later.
      if (!didMintConversation) ensureEvents(activeConversationId);

      try {
        await sendMessage(activeConversationId, text);
      } catch (error) {
        // The conversation may have been switched away from while the POST
        // was in flight -- the thread state is no longer this turn's, so
        // there is nothing left here to mark errored (mirrors the old
        // per-connection cursor guard's staleness check).
        if (conversationIdRef.current !== activeConversationId) return;
        const detail = error instanceof ApiError ? error.message : "Could not send the message";
        setMessages((prev) => markLastAssistantErrored(prev, detail));
        setIsSending(false);
        return;
      }

      if (didMintConversation && conversationIdRef.current === activeConversationId) {
        ensureEvents(activeConversationId);
      }
    },
    [ensureEvents, setMessages],
  );

  const hydrate = useCallback(
    (id: string, replay: ConversationReplay) => {
      if (id !== urlConversationId) return;
      hydratedConversationIdRef.current = id;
      setConversationId(id);
      setMessages((prev) => (prev.length > 0 ? prev : replay.messages));
      setIsLoadingHistory(false);
    },
    [urlConversationId, setMessages],
  );

  const reset = useCallback(() => {
    if (conversationIdRef.current) forgetInFlightTurn(conversationIdRef.current);
    eventsRef.current?.close();
    eventsRef.current = null;
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
