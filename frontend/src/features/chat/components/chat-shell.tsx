"use client";

import { BarChart3, Rows3, Shield, User } from "lucide-react";

import { AppHeader } from "@/components/layout/app-header";
import { AssistantMark } from "@/components/shared/assistant-mark";
import { Composer, type SuggestedPrompt } from "@/features/chat/components/composer";
import { MessageList } from "@/features/chat/components/message-list";
import { SidePanel } from "@/features/chat/components/side-panel";
import { useChatPanel } from "@/features/chat/hooks/use-chat-panel";
import { useChatThread } from "@/features/chat/hooks/use-chat-thread";
import type {
  EntityRef,
  MatchSummary,
  PlayerComparison,
  PlayerSummary,
  TeamSummary,
} from "@/features/chat/types";

const SUGGESTED_PROMPTS: SuggestedPrompt[] = [
  { label: "Compare Messi vs Mbappé", icon: <BarChart3 className="size-4 text-ink-muted" aria-hidden /> },
  { label: "How did Argentina perform defensively?", icon: <Shield className="size-4 text-ink-muted" aria-hidden /> },
  {
    label: "Show me the France vs Spain semifinal breakdown",
    icon: <Rows3 className="size-4 text-ink-muted" aria-hidden />,
  },
  { label: "Who scored the most goals per 90?", icon: <User className="size-4 text-ink-muted" aria-hidden /> },
  { label: "Which keeper made the most saves?", icon: <User className="size-4 text-ink-muted" aria-hidden /> },
];

function entityDisplayName(ref: EntityRef, data: unknown): string {
  switch (ref.type) {
    case "team":
      return (data as TeamSummary).name;
    case "match": {
      const match = data as MatchSummary;
      return `${match.homeTeam.name} vs ${match.awayTeam.name}`;
    }
    case "player":
      return (data as PlayerSummary).name;
    case "compare": {
      const comparison = data as PlayerComparison;
      return `${comparison.playerA.name} vs ${comparison.playerB.name}`;
    }
    default:
      return "this";
  }
}

/** Composes the whole chat page: header, thread/empty state, composer, side panel. */
export function ChatShell() {
  const { messages, isSending, submit, resolveEntity } = useChatThread();
  const panel = useChatPanel();

  const firstUserMessage = messages.find((m) => m.role === "user");
  const threadSummary =
    firstUserMessage?.parts[0]?.type === "text" ? firstUserMessage.parts[0].content : undefined;

  const openEntityData = panel.state.openEntity ? resolveEntity(panel.state.openEntity) : null;
  const composerPlaceholder =
    panel.state.openEntity && openEntityData
      ? `Ask a follow-up about ${entityDisplayName(panel.state.openEntity, openEntityData)}…`
      : messages.length > 0
        ? "Ask a follow-up…"
        : "Ask about a team, match or player…";

  const fromMessagePreview = (() => {
    const source = messages.find((m) => m.id === panel.state.sourceMessageId);
    const part = source?.parts[0];
    return part?.type === "text" ? part.content : "";
  })();

  return (
    <div className="flex h-dvh flex-col bg-surface-950">
      <AppHeader threadSummary={threadSummary} />
      <div className="flex min-h-0 grow">
        <div className="flex min-h-0 min-w-0 grow flex-col items-center">
          {messages.length === 0 ? (
            <div className="flex grow flex-col items-center justify-center gap-7 px-6 pb-12 md:px-12 md:pb-16">
              <div className="flex flex-col items-center gap-3 text-center">
                <AssistantMark size={48} radius="rounded-full" />
                <h1 className="text-heading-lg md:text-display-md">
                  Ask anything about World Cup 2026
                </h1>
                <p className="max-w-[560px] text-body-md text-ink-secondary md:text-body-lg">
                  Teams, matches and players, answered with tournament data: 104 matches, 48 teams.
                </p>
              </div>
              <Composer
                placeholder={composerPlaceholder}
                disabled={isSending}
                onSubmit={submit}
                suggestedPrompts={SUGGESTED_PROMPTS}
                onSelectPrompt={submit}
                className="w-full"
              />
            </div>
          ) : (
            <>
              <div className="min-h-0 w-full grow overflow-y-auto px-4 py-8">
                <div className="mx-auto flex w-full max-w-[720px] justify-center">
                  <MessageList
                    messages={messages}
                    openEntity={panel.state.openEntity}
                    onOpenEntity={panel.openEntity}
                  />
                </div>
              </div>
              <div className="w-full shrink-0 border-t border-border-subtle bg-surface-950 px-4 py-4">
                <Composer placeholder={composerPlaceholder} disabled={isSending} onSubmit={submit} />
              </div>
            </>
          )}
        </div>
        <SidePanel
          panelState={panel.state}
          resolveEntity={resolveEntity}
          fromMessagePreview={fromMessagePreview}
          onCollapse={panel.collapse}
          onExpand={panel.expand}
          onClose={panel.close}
          onJumpToMessage={panel.jumpToMessage}
        />
      </div>
    </div>
  );
}
