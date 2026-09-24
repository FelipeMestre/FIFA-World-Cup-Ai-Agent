import type { LiveServerEvent } from "@/features/chat/api/conversation-live";
import { parseMessageParts } from "@/features/chat/parse-message-parts";
import { messagePartSchema } from "@/features/chat/schemas/message-part.schema";
import type { ChatMessage, MessagePart } from "@/features/chat/types";

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `msg_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function textOf(message: ChatMessage): string | undefined {
  for (const part of message.parts) {
    if (part.type === "text") return part.content;
  }
  return undefined;
}

function streamingAssistant(): ChatMessage {
  return { id: makeId(), role: "assistant", parts: [], reasoning: "", isStreaming: true };
}

function userMessage(content: string): ChatMessage {
  return { id: makeId(), role: "user", parts: [{ type: "text", content }] };
}

/** Appends a content delta onto the last text part, or starts a new one. */
function appendTextDelta(parts: MessagePart[], delta: string): MessagePart[] {
  const last = parts[parts.length - 1];
  if (last?.type === "text") {
    return [...parts.slice(0, -1), { type: "text", content: last.content + delta }];
  }
  return [...parts, { type: "text", content: delta }];
}

function updateLastAssistant(
  messages: ChatMessage[],
  updater: (message: ChatMessage) => ChatMessage,
): ChatMessage[] {
  let next = messages;
  const last = messages[messages.length - 1];
  if (!last || last.role !== "assistant" || !last.isStreaming) {
    next = [...messages, streamingAssistant()];
  }
  const assistantId = next[next.length - 1]?.id;
  return next.map((message) => (message.id === assistantId ? updater(message) : message));
}

/**
 * Applies one live-socket event onto the thread. A `user_message` that
 * matches the optimistic bubble already on screen is ignored; the same
 * event on another window appends the user text and a streaming assistant.
 */
export function applyLiveEvent(messages: ChatMessage[], event: LiveServerEvent): ChatMessage[] {
  if (event.type === "rejected") {
    return updateLastAssistant(messages, (message) => ({
      ...message,
      error: event.detail,
      isStreaming: false,
      activeToolName: undefined,
    }));
  }

  if (event.type === "user_message") {
    const last = messages[messages.length - 1];
    const previous = messages[messages.length - 2];
    if (
      last?.role === "assistant" &&
      last.isStreaming &&
      previous?.role === "user" &&
      textOf(previous) === event.content
    ) {
      return messages;
    }
    if (last?.role === "user" && textOf(last) === event.content) {
      return [...messages, streamingAssistant()];
    }
    return [...messages, userMessage(event.content), streamingAssistant()];
  }

  switch (event.type) {
    case "reasoning_delta":
      return updateLastAssistant(messages, (message) => ({
        ...message,
        reasoning: (message.reasoning ?? "") + event.content,
      }));
    case "content_delta":
      return updateLastAssistant(messages, (message) => ({
        ...message,
        parts: appendTextDelta(message.parts, event.content),
      }));
    case "tool_call":
      return updateLastAssistant(messages, (message) => ({
        ...message,
        activeToolName: event.name,
      }));
    case "widget_ready": {
      const result = messagePartSchema.safeParse(event.part);
      if (!result.success) return messages;
      return updateLastAssistant(messages, (message) => ({
        ...message,
        parts: [...message.parts, result.data],
      }));
    }
    case "cap_reached":
      return updateLastAssistant(messages, (message) => ({
        ...message,
        parts: [{ type: "text", content: event.content }],
        clarification: event.clarification,
        activeToolName: undefined,
      }));
    case "message_done":
      return updateLastAssistant(messages, (message) => ({
        ...message,
        parts: message.clarification ? message.parts : parseMessageParts(event.parts),
        isStreaming: false,
        activeToolName: undefined,
      }));
    case "error":
      return updateLastAssistant(messages, (message) => ({
        ...message,
        error: event.detail,
        isStreaming: false,
        activeToolName: undefined,
      }));
    default:
      return messages;
  }
}

export function isTerminalLiveEvent(event: LiveServerEvent): boolean {
  return event.type === "message_done" || event.type === "error" || event.type === "rejected";
}
