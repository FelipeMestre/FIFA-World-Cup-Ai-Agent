"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";

import { AssistantMark } from "@/components/shared/assistant-mark";

/** The visitor's own message, right-aligned on the violet-tinted user surface. */
export function UserBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[520px] rounded-md bg-chat-user-surface px-4 py-2.5 text-body-lg text-ink-primary">
        {children}
      </div>
    </div>
  );
}

/** The assistant's reply: mark + bubble on surface-800, widgets slot in below. */
export function AssistantBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <AssistantMark size={32} radius="rounded-full" />
      <div className="flex flex-col items-start gap-3">{children}</div>
    </div>
  );
}

export function AssistantText({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-[640px] rounded-md bg-surface-800 px-4 py-3 text-body-lg text-ink-primary">
      {children}
    </div>
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
