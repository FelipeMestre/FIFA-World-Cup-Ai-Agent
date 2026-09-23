import { messagePartSchema } from "@/features/chat/schemas/message-part.schema";
import type { RawMessagePart } from "@/features/chat/schemas/message-part.schema";
import type { MessagePart } from "@/features/chat/types";

/**
 * Validates each raw part from `message_done` or a replay payload against
 * the widget contract. A part that fails validation is dropped rather than
 * crashing the thread -- see message-part-renderer.tsx for the visible
 * fallback shown in that case.
 */
export function parseMessageParts(rawParts: RawMessagePart[]): MessagePart[] {
  const parts: MessagePart[] = [];
  for (const rawPart of rawParts) {
    const result = messagePartSchema.safeParse(rawPart);
    if (result.success) {
      parts.push(result.data);
    }
  }
  return parts;
}
