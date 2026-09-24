import { fetchJson } from "@/lib/api/client";
import {
  conversationSummaryListSchema,
  toConversationSummary,
} from "@/features/chat/schemas/conversation.schema";
import type { ConversationSummary } from "@/features/chat/types";

export async function listConversations(): Promise<ConversationSummary[]> {
  const payload = await fetchJson<unknown>("/api/conversations");
  return conversationSummaryListSchema.parse(payload).map(toConversationSummary);
}
