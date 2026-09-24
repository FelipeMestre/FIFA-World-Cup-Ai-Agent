import type { ConversationSummary } from "@/features/chat/types";

export interface GroupedConversations {
  today: ConversationSummary[];
  earlier: ConversationSummary[];
}

function isSameLocalDay(iso: string, now: Date): boolean {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return false;
  }
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

/** Splits a recency-ordered list into the sidebar's Today / Earlier groups. */
export function groupConversations(
  conversations: ConversationSummary[],
  now: Date = new Date(),
): GroupedConversations {
  const today: ConversationSummary[] = [];
  const earlier: ConversationSummary[] = [];
  for (const conversation of conversations) {
    if (isSameLocalDay(conversation.updatedAt, now)) {
      today.push(conversation);
    } else {
      earlier.push(conversation);
    }
  }
  return { today, earlier };
}
