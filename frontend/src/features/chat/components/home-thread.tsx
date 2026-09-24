"use client";

import type { ReactNode } from "react";

import { MessageList } from "@/features/chat/components/message-list";
import type { ChatMessage, EntityRef } from "@/features/chat/types";

/**
 * The active-thread state of the home page (HomeActive.dc.html): just the
 * question/answer turns. The thread's top bar lives in `ThreadHeader`
 * (rendered by home-shell.tsx above this AND the side panel) and the
 * follow-up composer is `ThreadComposer` (rendered by `HomeShell` as a
 * layout sibling below the scroll area) -- see each component's docstring
 * for why they're not part of this one.
 */
export function HomeThread({
  messages,
  openEntity,
  onOpenEntity,
  onRegenerate,
  children,
}: {
  messages: ChatMessage[];
  openEntity: EntityRef | null;
  onOpenEntity: (ref: EntityRef, sourceMessageId: string) => void;
  onRegenerate: (question: string) => void;
  /**
   * The routed page's SSR-resolved content -- `ConversationHydrator` today,
   * which renders `null` once hydrated. Rendered here, in the same wrapper
   * as `MessageList`, so its loading `<Suspense>` fallback (the message
   * skeleton) actually appears inside the chat surface instead of above
   * the whole page.
   */
  children?: ReactNode;
}) {
  return (
    <div className="mx-auto flex w-full min-w-0 max-w-[760px] grow flex-col self-center px-4 py-10 md:px-6">
      {children}
      <MessageList
        messages={messages}
        openEntity={openEntity}
        onOpenEntity={onOpenEntity}
        onRegenerate={onRegenerate}
      />
    </div>
  );
}
