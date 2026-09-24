"use client";

import { useCallback, useEffect, useState } from "react";

import { listConversations } from "@/features/chat/api/list-conversations";
import { updateConversationTitle } from "@/features/chat/api/update-conversation-title";
import { connectUserEvents, type UserEvent } from "@/features/chat/api/user-events";
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

  /**
   * Patches a row's title/icon in place from a live `conversation_updated`
   * SSE event -- no refetch, and (unlike `rename`) no reordering, since a
   * background categorization event is not a user-initiated action.
   */
  const applyConversationUpdate = useCallback(
    (conversationId: string, patch: { title: string; icon: string }) => {
      setConversations((prev) =>
        prev.map((row) => (row.id === conversationId ? { ...row, ...patch } : row)),
      );
    },
    [],
  );

  /**
   * Prepends a row for a brand-new conversation from a live
   * `conversation_created` event -- deduped by id, since the window that
   * itself created the conversation may already have it from the existing
   * `isSending`-toggle `refreshConversations()` in `home-shell.tsx`. Same
   * defensive shape `rename` already uses, which also self-heals if a stale
   * entry existed for some reason.
   */
  const addCreatedConversation = useCallback((event: {
    conversationId: string;
    title: string;
    createdAt: string;
  }) => {
    setConversations((prev) => {
      if (prev.some((row) => row.id === event.conversationId)) return prev;
      const created: ConversationSummary = {
        id: event.conversationId,
        title: event.title,
        icon: null,
        updatedAt: event.createdAt,
        createdAt: event.createdAt,
        isGenerating: false,
      };
      return [created, ...prev];
    });
  }, []);

  /**
   * Owns the per-user SSE connection for as long as this hook (and the
   * sidebar mounting it, `HomeShell`) is mounted -- opened once on mount,
   * unlike the per-conversation connection, which only opens once a
   * conversation is selected. Handles both event kinds internally:
   * `conversation_created` prepends a row, `conversation_updated` patches
   * one in place via `applyConversationUpdate`.
   */
  useEffect(() => {
    const handleEvent = (event: UserEvent) => {
      if (event.type === "conversation_created") {
        addCreatedConversation({
          conversationId: event.conversation_id,
          title: event.title,
          createdAt: event.created_at,
        });
        return;
      }
      applyConversationUpdate(event.conversation_id, { title: event.title, icon: event.icon });
    };

    const connection = connectUserEvents(handleEvent);
    return () => connection.close();
  }, [addCreatedConversation, applyConversationUpdate]);

  return { conversations, isLoading, loadError, refresh, rename, applyConversationUpdate };
}
