"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { ConversationReplay } from "@/features/chat/api/get-conversation-messages";

type HydrateFn = (conversationId: string, replay: ConversationReplay) => void;

const ThreadHydrationContext = createContext<HydrateFn | null>(null);

export function ThreadHydrationProvider({
  value,
  children,
}: {
  value: HydrateFn;
  children: ReactNode;
}) {
  return (
    <ThreadHydrationContext.Provider value={value}>{children}</ThreadHydrationContext.Provider>
  );
}

export function useThreadHydration(): HydrateFn {
  const fn = useContext(ThreadHydrationContext);
  if (!fn) {
    throw new Error("useThreadHydration must be used within a ThreadHydrationProvider");
  }
  return fn;
}
