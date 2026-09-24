"use client";

import { History, Plus, User } from "lucide-react";

import { AssistantMark } from "@/components/shared/assistant-mark";
import { Button } from "@/components/ui/button";

/**
 * Application-wide top bar. Desktop matches Main.dc.html / HomeActive.dc.html
 * (64px, full labels, World Cup badge, account avatar); mobile matches
 * MobileEmpty.dc.html / MobileChat.dc.html (56px, icon-only actions, no
 * badge or account avatar -- design/canvas.json's mobile note: "Widgets
 * reflow at 358px"). History and New chat are decorative in this build --
 * no history/threads persistence exists yet, so they're presentational only.
 */
export function AppHeader({ threadSummary }: { threadSummary?: string }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-ds-2 border-b border-border-subtle bg-surface-900 px-ds-4 md:h-16 md:gap-ds-3 md:px-ds-6">
      <AssistantMark size={28} className="md:hidden" />
      <AssistantMark size={32} className="hidden md:flex" />
      <span className="truncate text-heading-sm md:text-heading-md">Football Ai Scout</span>
      <span className="hidden h-[22px] items-center rounded-sm border border-border-strong px-ds-2 text-label-sm text-ink-secondary md:flex">
        World Cup 2026
      </span>
      {threadSummary ? (
        <span className="ml-ds-3 hidden truncate text-body-md text-ink-secondary md:inline">
          {threadSummary}
        </span>
      ) : null}
      <div className="grow" />
      <Button
        type="button"
        variant="outline"
        aria-label="History"
        className="size-11 border-border-strong bg-transparent p-0 text-ink-primary hover:bg-surface-700 md:h-10 md:w-auto md:gap-ds-2 md:px-3"
      >
        <History className="size-4" aria-hidden />
        <span className="hidden md:inline">History</span>
      </Button>
      <Button
        type="button"
        variant="outline"
        aria-label="New chat"
        className="size-11 border-border-strong bg-transparent p-0 text-ink-primary hover:bg-surface-700 md:h-10 md:w-auto md:gap-ds-2 md:px-3"
      >
        <Plus className="size-4" aria-hidden />
        <span className="hidden md:inline">New chat</span>
      </Button>
      <Button
        type="button"
        variant="outline"
        aria-label="Account"
        size="icon"
        className="hidden size-10 rounded-full border-border-strong bg-surface-700 text-ink-secondary hover:bg-surface-600 md:flex"
      >
        <User className="size-[18px]" aria-hidden />
      </Button>
    </header>
  );
}
