/**
 * Wire events for the per-user SSE stream (`GET /users/events`, proxied
 * through `app/api/users/events/route.ts`). Unlike
 * `@/features/chat/api/conversation-events`, this connection carries no
 * conversation id -- it is the authenticated user's own account-wide event
 * stream, opened once by `useConversationList` for as long as the sidebar
 * is mounted, not gated on any conversation being selected.
 */

/**
 * Emitted on the `conversation_created` SSE event, once per brand-new
 * conversation, from `ChatService.start_turn`. Delivered to every device
 * with this user's sidebar mounted, regardless of which (if any)
 * conversation is on screen there.
 */
export interface ConversationCreatedEvent {
  type: "conversation_created";
  conversation_id: string;
  title: string;
  created_at: string;
  cursor: string;
}

/**
 * Emitted on the `conversation_updated` SSE event once
 * `categorize_conversation_task` resolves a title + icon for a
 * conversation.
 */
export interface ConversationUpdatedEvent {
  type: "conversation_updated";
  conversation_id: string;
  title: string;
  icon: string;
  cursor: string;
}

export type UserEvent = ConversationCreatedEvent | ConversationUpdatedEvent;

export interface UserEventsConnection {
  close: () => void;
}

/**
 * Opens the per-user SSE connection. `EventSource` reconnects natively on a
 * drop and the backend resumes from the last delivered id via the
 * `Last-Event-ID` header it sends automatically -- same native-resume
 * pattern as `connectConversationEvents`.
 *
 * Hits our own Next.js proxy route, never the FastAPI backend directly:
 * `EventSource` cannot set an `Authorization` header, so the proxy route
 * holds the session cookie server-side instead.
 */
export function connectUserEvents(onEvent: (event: UserEvent) => void): UserEventsConnection {
  const source = new EventSource("/api/users/events");

  const handleFrame = (message: MessageEvent<string>) => {
    try {
      onEvent(JSON.parse(message.data) as UserEvent);
    } catch {
      // Ignore a frame that is not the JSON vocabulary above.
    }
  };

  source.addEventListener("conversation_created", handleFrame);
  source.addEventListener("conversation_updated", handleFrame);

  return {
    close() {
      source.close();
    },
  };
}
