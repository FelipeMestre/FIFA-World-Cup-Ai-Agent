"use client";

import { useCallback, useEffect, useState } from "react";

import { listConversations } from "@/features/chat/api/list-conversations";
import { updateConversationTitle } from "@/features/chat/api/update-conversation-title";
import type { ConversationSummary } from "@/features/chat/types";

export function useConversationList() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const items = await listConversations();
      setConversations(items);
      setLoadError(null);
    } catch {
      setLoadError("Couldn't load conversations");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const rename = useCallback(async (conversationId: string, title: string) => {
    const updated = await updateConversationTitle(conversationId, title);
    setConversations((prev) => [updated, ...prev.filter((row) => row.id !== conversationId)]);
    return updated;
  }, []);

  return { conversations, isLoading, loadError, refresh, rename };
}
