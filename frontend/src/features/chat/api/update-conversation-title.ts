import { fetchJson } from "@/lib/api/client";
import {
  conversationSummarySchema,
  toConversationSummary,
} from "@/features/chat/schemas/conversation.schema";
import type { ConversationSummary } from "@/features/chat/types";

export async function updateConversationTitle(
  conversationId: string,
  title: string,
): Promise<ConversationSummary> {
  const payload = conversationSummarySchema.parse(
    await fetchJson<unknown>(`/api/conversations/${conversationId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }),
  );
  return toConversationSummary(payload);
}
