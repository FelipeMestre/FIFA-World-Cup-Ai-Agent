"use client";

import { useState, type ReactNode } from "react";
import { Check, ChevronDown, ChevronRight, Copy, RotateCw, Wrench } from "lucide-react";

import { AssistantMark } from "@/components/shared/assistant-mark";

/**
 * The visitor's own message, right-aligned on the violet-tinted user surface.
 * The flattened bottom-right corner (4px against 18px elsewhere) points the
 * bubble at its author, per HomeActive.dc.html.
 */
export function UserBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[520px] rounded-[18px] rounded-br-[4px] border border-brand/28 bg-chat-user-surface px-[18px] py-3 text-body-lg text-ink-primary">
        {children}
      </div>
    </div>
  );
}

/**
 * The assistant's reply (HomeActive.dc.html): an attribution row above the
 * answer, which then runs full width -- not a bubble beside the mark, so the
 * 640px-wide widgets below line up with the prose.
 */
export function AssistantBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex items-center gap-2.5">
        <AssistantMark
          size={28}
          radius="rounded-md"
          className="shadow-[0_4px_12px_rgba(78,142,247,0.3)]"
        />
        <span className="text-body-md font-semibold text-ink-primary">Scout</span>
      </div>
      {children}
    </div>
  );
}

export function AssistantText({ children }: { children: ReactNode }) {
  return (
    <p className="max-w-[680px] text-body-lg leading-[26px] text-ink-secondary">{children}</p>
  );
}

/**
 * Collapsed-by-default, italicized "reasoning trace" region above the final
 * content -- fills in incrementally as `reasoning_delta` events arrive,
 * matching the Claude/ChatGPT-style reasoning-trace pattern. Renders nothing
 * once there is no reasoning content.
 */
export function ReasoningBlock({
  content,
  isStreaming,
}: {
  content: string;
  isStreaming?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  if (!content) {
    return null;
  }

  return (
    <div className="flex max-w-[640px] flex-col gap-1 text-body-md text-ink-muted">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-fit items-center gap-1 italic"
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown className="size-3.5" aria-hidden />
        ) : (
          <ChevronRight className="size-3.5" aria-hidden />
        )}
        {isStreaming ? "Thinking…" : "Reasoning"}
      </button>
      {expanded ? <p className="whitespace-pre-wrap italic">{content}</p> : null}
    </div>
  );
}

/** Lightweight in-progress indicator while the tool-execution loop dispatches a call. */
export function ToolCallIndicator({ name }: { name: string }) {
  return (
    <div className="flex items-center gap-1 text-body-md italic text-ink-muted">
      <Wrench className="size-3.5" aria-hidden />
      <span>Using {name}…</span>
    </div>
  );
}

/**
 * Copy / regenerate row under a finished answer (HomeActive.dc.html). The
 * design also shows a follow-up suggestion here; the backend sends no such
 * field, so it is left out rather than faked.
 */
export function AnswerActions({
  answerText,
  onRegenerate,
}: {
  answerText: string;
  onRegenerate?: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(answerText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard is unavailable without a secure context or permission;
      // silently leaving the button idle is better than an error toast here.
    }
  }

  return (
    <div className="flex items-center gap-1 text-ink-muted">
      <button
        type="button"
        onClick={copy}
        aria-label={copied ? "Answer copied" : "Copy answer"}
        className="focus-ring flex size-8 items-center justify-center rounded-md hover:bg-surface-800"
      >
        {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
      </button>
      {onRegenerate ? (
        <button
          type="button"
          onClick={onRegenerate}
          aria-label="Regenerate"
          className="focus-ring flex size-8 items-center justify-center rounded-md hover:bg-surface-800"
        >
          <RotateCw className="size-4" aria-hidden />
        </button>
      ) : null}
    </div>
  );
}

/**
 * Subtle inline note for the tool loop's iteration-cap clarification ask --
 * visually distinct from the assistant's main text, but not a full
 * error/alert state.
 */
export function ClarificationNote({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-[640px] border-l-2 border-border-subtle pl-3 text-body-md italic text-ink-secondary">
      {children}
    </div>
  );
}
