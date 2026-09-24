import { z } from "zod";

import type { ConversationSummary } from "@/features/chat/types";

export const conversationSummarySchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  icon: z.string().nullable().default(null),
  updated_at: z.string(),
  created_at: z.string(),
  is_generating: z.boolean().default(false),
});

export const conversationSummaryListSchema = z.array(conversationSummarySchema);

export function toConversationSummary(
  row: z.infer<typeof conversationSummarySchema>,
): ConversationSummary {
  return {
    id: row.id,
    title: row.title,
    icon: row.icon,
    updatedAt: row.updated_at,
    createdAt: row.created_at,
    isGenerating: row.is_generating,
  };
}
