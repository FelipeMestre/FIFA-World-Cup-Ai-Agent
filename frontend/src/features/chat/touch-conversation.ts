import type { ConversationSummary } from "@/features/chat/types";

/**
 * Moves the row `conversationId` to the top of the list with the server's
 * new `updatedAt`, keeping every other field. Pure and idempotent: replaying
 * the same event yields the same list, and a stale event (older than the
 * row's current `updatedAt`) or an id not in the list leaves it untouched.
 */
export function touchConversation(
  rows: ConversationSummary[],
  conversationId: string,
  updatedAt: string,
): ConversationSummary[] {
  const current = rows.find((row) => row.id === conversationId);
  if (current === undefined) return rows;
  if (Date.parse(updatedAt) < Date.parse(current.updatedAt)) return rows;
  return [{ ...current, updatedAt }, ...rows.filter((row) => row.id !== conversationId)];
}
