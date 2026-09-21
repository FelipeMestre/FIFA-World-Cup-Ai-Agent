"use client";

import { useState, type KeyboardEvent } from "react";
import { ArrowUp, Share } from "lucide-react";

import { MessageList } from "@/features/chat/components/message-list";
import type { ChatMessage, EntityRef } from "@/features/chat/types";

/**
 * The active-thread state of the home page (HomeActive.dc.html): thread
 * header, the question/answer turns, and a sticky follow-up composer that
 * fades the thread out behind it.
 *
 * Share is presentational -- no share/permalink backend exists yet.
 */
export function HomeThread({
  title,
  messages,
  isSending,
  openEntity,
  onSubmit,
  onOpenEntity,
  onRegenerate,
}: {
  title: string;
  messages: ChatMessage[];
  isSending: boolean;
  openEntity: EntityRef | null;
  onSubmit: (message: string) => void;
  onOpenEntity: (ref: EntityRef, sourceMessageId: string) => void;
  onRegenerate: (question: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const answerCount = messages.filter((message) => message.role === "assistant").length;

  function send() {
    const trimmed = draft.trim();
    if (!trimmed || isSending) return;
    onSubmit(trimmed);
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  return (
    <>
      <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-border-subtle bg-surface-950/72 px-7 backdrop-blur-[12px]">
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

      <div className="mx-auto flex w-full max-w-[760px] grow flex-col px-4 py-10 md:px-0">
        <MessageList
          messages={messages}
          openEntity={openEntity}
          onOpenEntity={onOpenEntity}
          onRegenerate={onRegenerate}
        />
      </div>

      <div className="sticky bottom-0 z-20 flex shrink-0 flex-col items-center gap-2.5 bg-gradient-to-b from-transparent to-surface-950 to-40% px-4 pt-5 pb-7 md:px-0">
        <div className="flex w-full max-w-[760px] items-center gap-2.5 rounded-[20px] border border-border-strong bg-surface-800 py-2 pr-2 pl-5 shadow-[0_24px_60px_rgba(2,3,5,0.6),inset_0_1px_0_rgba(244,246,249,0.06)]">
          <label htmlFor="thread-composer" className="sr-only">
            Ask a follow-up
          </label>
          <textarea
            id="thread-composer"
            rows={1}
            value={draft}
            disabled={isSending}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a follow-up…"
            className="h-11 grow resize-none border-0 bg-transparent py-2.5 font-sans text-body-lg text-ink-primary placeholder:text-ink-muted focus:outline-none disabled:opacity-60"
          />
          <button
            type="button"
            className="focus-ring hidden h-8 shrink-0 items-center gap-1.5 rounded-full border border-border-strong bg-surface-700 px-2.5 text-body-sm text-ink-secondary hover:bg-surface-600 md:flex"
          >
            <span className="font-mono text-ink-primary">@</span> Mention
          </button>
          <button
            type="button"
            aria-label="Send"
            onClick={send}
            disabled={isSending || draft.trim().length === 0}
            className="focus-ring flex size-11 shrink-0 items-center justify-center rounded-[14px] bg-brand text-on-brand shadow-[0_6px_18px_rgba(126,111,238,0.45),inset_0_1px_0_rgba(255,255,255,0.25)] disabled:opacity-40"
          >
            <ArrowUp className="size-[18px]" aria-hidden />
          </button>
        </div>
        {/* Absent on mobile in MobileChat.dc.html. */}
        <span className="hidden text-body-sm text-ink-muted md:block">
          Covers results, events, lineups and match stats. No passing or tracking data.
        </span>
      </div>
    </>
  );
}
