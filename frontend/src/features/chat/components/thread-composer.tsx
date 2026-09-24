"use client";

import { useState, type KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";

/**
 * The active-thread's follow-up composer. Deliberately a sibling of the
 * scrollable message list (`HomeThread`), not nested inside it: it used to
 * live inside the scroll container as a `sticky bottom-0` bar, which
 * overlaid the last few pixels of scrolled content -- `MessageList`'s
 * scroll-to-bottom effect put the newest message flush with the bottom of
 * the scroll container, which is exactly where the sticky bar sat, hiding
 * it. As a true layout sibling below the scroll area, there's nothing left
 * for it to cover.
 */
export function ThreadComposer({
  isSending,
  onSubmit,
}: {
  isSending: boolean;
  onSubmit: (message: string) => void;
}) {
  const [draft, setDraft] = useState("");

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
    <div className="z-20 flex w-full min-w-0 shrink-0 flex-col items-center gap-2.5 bg-surface-950 px-4 pt-5 pb-7 md:px-6">
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
  );
}
