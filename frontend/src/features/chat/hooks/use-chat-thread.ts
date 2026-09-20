"use client";

import { useCallback, useMemo, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { sendMessage } from "@/features/chat/api/send-message";
import { messagePartSchema } from "@/features/chat/schemas/message-part.schema";
import type { RawMessagePart } from "@/features/chat/schemas/message-part.schema";
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
 * Validates each raw part from a `message_done` event against the widget
 * contract schema. A part that fails validation (e.g. a future
 * `team_widget` whose `data` shape doesn't match yet) is dropped rather than
 * crashing the thread -- see message-part-renderer.tsx for the visible
 * fallback shown to the user in that case.
 */
function parseMessageParts(rawParts: RawMessagePart[]): MessagePart[] {
  const parts: MessagePart[] = [];
  for (const rawPart of rawParts) {
    const result = messagePartSchema.safeParse(rawPart);
    if (result.success) {
      parts.push(result.data);
    }
  }
  return parts;
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
      const assistantId = makeId();
      const draftAssistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        parts: [],
        reasoning: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMessage, draftAssistantMessage]);
      setIsSending(true);

      const updateAssistant = (updater: (message: ChatMessage) => ChatMessage) => {
        setMessages((prev) =>
          prev.map((message) => (message.id === assistantId ? updater(message) : message)),
        );
      };

      try {
        for await (const event of sendMessage(conversationId, text)) {
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
              setConversationId(event.conversation_id);
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
      } finally {
        setIsSending(false);
      }
    },
    [conversationId],
  );

  return { messages, isSending, submit, resolveEntity };
}
