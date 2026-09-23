import { z } from "zod";

import { fetchJson } from "@/lib/api/client";
import { parseMessageParts } from "@/features/chat/parse-message-parts";
import type { RawMessagePart } from "@/features/chat/schemas/message-part.schema";
import type { ChatMessage } from "@/features/chat/types";

const replayMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  parts: z.array(z.unknown()),
  created_at: z.string(),
});

const replaySchema = z.object({
  conversation_id: z.string().uuid(),
  title: z.string(),
  messages: z.array(replayMessageSchema),
});

export interface ConversationReplay {
  conversationId: string;
  title: string;
  messages: ChatMessage[];
}

/** Shared by the client fetch below and the server-fetched path in `[conversationId]/page.tsx`. */
export function parseConversationReplay(payload: unknown): ConversationReplay {
  const parsed = replaySchema.parse(payload);
  return {
    conversationId: parsed.conversation_id,
    title: parsed.title,
    messages: parsed.messages.map((message, index) => ({
      id: `${parsed.conversation_id}:${index}`,
      role: message.role,
      parts: parseMessageParts(message.parts as RawMessagePart[]),
    })),
  };
}

export async function getConversationMessages(
  conversationId: string,
): Promise<ConversationReplay> {
  return parseConversationReplay(
    await fetchJson<unknown>(`/api/conversations/${conversationId}/messages`),
  );
}
