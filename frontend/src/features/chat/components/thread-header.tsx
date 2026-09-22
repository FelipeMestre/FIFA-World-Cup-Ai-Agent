"use client";

import { Share } from "lucide-react";

import type { ChatMessage } from "@/features/chat/types";

/**
 * The active thread's top bar: title, answer count, Share. Rendered above
 * both the thread column and the side panel (home-shell.tsx), so it spans
 * the full width of that combined area -- the panel starts right where this
 * bar ends, with no gap and no separate header of its own duplicating it.
 *
 * Share is presentational -- no share/permalink backend exists yet.
 */
export function ThreadHeader({
  title,
  messages,
}: {
  title: string;
  messages: ChatMessage[];
}) {
  const answerCount = messages.filter(
    (message) => message.role === "assistant",
  ).length;

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border-subtle bg-surface-950/72 px-7 backdrop-blur-[12px]">
      <span className="truncate text-heading-sm">{title}</span>
      <span className="flex h-6 shrink-0 items-center rounded-full border border-border-subtle bg-surface-800 px-2 font-mono text-[12px] text-ink-muted">
        {answerCount} {answerCount === 1 ? "answer" : "answers"}
      </span>
      <div className="grow" />
      <button
        type="button"
        className="focus-ring flex h-9 shrink-0 items-center gap-2 rounded-lg border border-border-strong px-3 text-body-sm font-semibold text-ink-primary hover:bg-surface-800"
      >
        <Share className="size-4" aria-hidden />
        Share
      </button>
    </header>
  );
}
