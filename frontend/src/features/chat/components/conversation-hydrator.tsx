"use client";

import { useEffect } from "react";

import { useThreadHydration } from "@/features/chat/thread-hydration-context";
import type { ConversationReplay } from "@/features/chat/api/get-conversation-messages";

/** Reports a server-fetched conversation replay into useChatThread's state, once per (conversationId, replay). Renders nothing. */
export function ConversationHydrator({
  conversationId,
  replay,
}: {
  conversationId: string;
  replay: ConversationReplay;
}) {
  const hydrate = useThreadHydration();
  useEffect(() => {
    hydrate(conversationId, replay);
  }, [conversationId, replay, hydrate]);
  return null;
}
