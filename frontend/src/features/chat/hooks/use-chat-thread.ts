"use client";

import { useCallback, useMemo, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { sendMessage } from "@/features/chat/api/send-message";
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

/**
 * Owns the message thread and the conversation id, and calls the chat API.
 * Also derives an entity registry (id -> widget data) from every widget
 * part seen so far, so the side panel can resolve an `EntityRef` without a
 * separate fetch -- the data already arrived inline with the message.
 */
export function useChatThread() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

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
      setMessages((prev) => [...prev, userMessage]);
      setIsSending(true);

      try {
        const result = await sendMessage(conversationId, text);
        setConversationId(result.conversationId);
        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: "assistant", parts: result.parts },
        ]);
      } catch (error) {
        const detail =
          error instanceof ApiError
            ? error.message
            : "The chat assistant is temporarily unavailable";
        setMessages((prev) => [
          ...prev,
          { id: makeId(), role: "assistant", parts: [], error: detail },
        ]);
      } finally {
        setIsSending(false);
      }
    },
    [conversationId],
  );

  return { messages, isSending, submit, resolveEntity };
}
