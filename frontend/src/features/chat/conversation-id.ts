const CONVERSATION_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isConversationId(value: string): boolean {
  return CONVERSATION_ID_PATTERN.test(value);
}

export function newConversationId(): string {
  return crypto.randomUUID();
}

/** Matches `UpdateConversationTitleRequest.title` max_length on the backend. */
export const CONVERSATION_TITLE_MAX_LENGTH = 200;

export type ParsedHomeConversation =
  | { status: "empty" }
  | { status: "ok"; id: string }
  | { status: "invalid" };

/**
 * Maps the optional catch-all `[[...conversationId]]` segment to a single
 * UUID (`/home/<uuid>`), empty (`/home`), or invalid (anything else).
 */
export function parseHomeConversationSegments(
  segments: string[] | undefined,
): ParsedHomeConversation {
  if (segments === undefined || segments.length === 0) {
    return { status: "empty" };
  }
  if (segments.length === 1 && isConversationId(segments[0])) {
    return { status: "ok", id: segments[0] };
  }
  return { status: "invalid" };
}
