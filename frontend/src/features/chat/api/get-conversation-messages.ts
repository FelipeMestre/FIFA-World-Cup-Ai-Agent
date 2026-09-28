import { z } from "zod";

import { fetchJson } from "@/lib/api/client";
import { parseMessageParts } from "@/features/chat/parse-message-parts";
import type { RawMessagePart } from "@/features/chat/schemas/message-part.schema";
import type { ChatMessage } from "@/features/chat/types";

const replayMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  parts: z.array(z.unknown()),
  created_at: z.string(),
  metadata: z
    .object({ match_selector: z.object({ match_id: z.number(), label: z.string() }).optional() })
    .nullable()
    .optional(),
});

const replaySchema = z.object({
  conversation_id: z.string().uuid(),
  title: z.string(),
  messages: z.array(replayMessageSchema),
  last_turn_failure: z.string().nullable().optional(),
});

export interface ConversationReplay {
  conversationId: string;
  title: string;
  messages: ChatMessage[];
}

/** Shared by the client fetch below and the server-fetched path in `[conversationId]/page.tsx`. */
export function parseConversationReplay(payload: unknown): ConversationReplay {
  const parsed = replaySchema.parse(payload);
  const messages: ChatMessage[] = parsed.messages.map((message, index) => ({
    id: `${parsed.conversation_id}:${index}`,
    role: message.role,
    parts: parseMessageParts(message.parts as RawMessagePart[]),
    metadata: message.metadata?.match_selector
      ? {
          matchSelector: {
            matchId: message.metadata.match_selector.match_id,
            label: message.metadata.match_selector.label,
          },
        }
      : null,
  }));

  // `last_turn_failure` is only ever set by the backend when the failed
  // user message is still the last one -- a synthetic, part-less assistant
  // message with `error` set reuses `MessageList`'s existing error-bubble
  // rendering (the same one a live-stream failure already produces) rather
  // than needing a second UI path just for the reload case.
  if (parsed.last_turn_failure) {
    messages.push({
      id: `${parsed.conversation_id}:failure`,
      role: "assistant",
      parts: [],
      error: parsed.last_turn_failure,
    });
  }

  return {
    conversationId: parsed.conversation_id,
    title: parsed.title,
    messages,
  };
}

export async function getConversationMessages(
  conversationId: string,
  signal?: AbortSignal,
): Promise<ConversationReplay> {
  return parseConversationReplay(
    await fetchJson<unknown>(`/api/conversations/${conversationId}/messages`, { signal }),
  );
}
