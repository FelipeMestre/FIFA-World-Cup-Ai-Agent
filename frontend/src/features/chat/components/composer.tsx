"use client";

import { useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";

import { cn } from "@/lib/utils";

export interface SuggestedPrompt {
  label: string;
  icon: React.ReactNode;
}

/**
 * The chat input (Main.dc.html / HomeActive.dc.html). The placeholder names
 * the pinned entity when the side panel is open, per design/README.md's
 * panel-behavior rule.
 */
export function Composer({
  placeholder,
  disabled,
  onSubmit,
  suggestedPrompts,
  onSelectPrompt,
  helperText = "Covers results, events, lineups and match stats. No passing or tracking data.",
  className,
}: {
  placeholder: string;
  disabled?: boolean;
  onSubmit: (message: string) => void;
  suggestedPrompts?: SuggestedPrompt[];
  onSelectPrompt?: (label: string) => void;
  helperText?: string;
  className?: string;
}) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <div className={cn("flex flex-col items-center gap-ds-2", className)}>
      <form
        onSubmit={handleSubmit}
        className="flex w-full max-w-[720px] items-center gap-ds-3 rounded-xl border border-border-strong bg-surface-700 py-2.5 pr-2.5 pl-5 shadow-sm"
      >
        <label htmlFor="composer-input" className="sr-only">
          {placeholder}
        </label>
        <textarea
          id="composer-input"
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="h-11 grow resize-none bg-transparent py-2.5 text-body-lg text-ink-primary placeholder:text-ink-muted focus:outline-none disabled:opacity-60"
        />
        <button
          type="submit"
          aria-label="Send"
          disabled={disabled || value.trim().length === 0}
          className="focus-ring flex size-11 shrink-0 items-center justify-center rounded-full bg-brand text-on-brand disabled:opacity-40"
        >
          <ArrowUp className="size-5" aria-hidden />
        </button>
      </form>

      {suggestedPrompts && suggestedPrompts.length > 0 ? (
        <div className="flex w-full max-w-[800px] flex-wrap justify-center gap-ds-2">
          {suggestedPrompts.map((prompt) => (
            <button
              key={prompt.label}
              type="button"
              onClick={() => onSelectPrompt?.(prompt.label)}
              className="focus-ring flex h-11 items-center gap-ds-2 rounded-full border border-border-strong bg-surface-900 px-ds-4 text-body-md text-ink-primary hover:bg-surface-800"
            >
              {prompt.icon}
              {prompt.label}
            </button>
          ))}
        </div>
      ) : null}

      {/* Absent on mobile in both MobileEmpty.dc.html and MobileChat.dc.html. */}
      {helperText ? (
        <p className="hidden text-body-sm text-ink-muted md:block">{helperText}</p>
      ) : null}
    </div>
  );
}
