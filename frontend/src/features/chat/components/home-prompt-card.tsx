"use client";

import { ArrowRight } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Home page suggested prompt card (HomeActive.dc.html).
 * Four cards in a 2x2 grid: each has a tinted icon circle, title, hint, and chevron.
 */
export function HomePromptCard({
  title,
  hint,
  iconPath,
  tintClass,
  inkColor,
  onClick,
}: {
  title: string;
  hint: string;
  iconPath: string;
  tintClass: string;
  inkColor: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "focus-ring min-h-[72px] flex items-center gap-ds-3 rounded-lg px-4 py-3.5",
        "border border-border-subtle bg-surface-900/72",
        "text-ink-primary text-left cursor-pointer",
        "shadow-[inset_0_1px_0_rgba(244,246,249,0.04)]",
        "transition-colors hover:bg-surface-800/80",
      )}
    >
      <span
        className={cn(
          "shrink-0 flex size-10 items-center justify-center rounded-lg",
          tintClass,
        )}
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 20 20"
          fill="none"
          stroke={inkColor}
          strokeWidth="1.75"
          strokeLinecap="square"
          aria-hidden="true"
        >
          <path d={iconPath} />
        </svg>
      </span>
      <span className="flex-1 min-w-0 flex flex-col gap-0.5">
        <span className="text-heading-sm truncate">{title}</span>
        <span className="text-body-sm text-ink-muted truncate">{hint}</span>
      </span>
      <ArrowRight className="size-4 shrink-0 text-ink-muted" aria-hidden />
    </button>
  );
}