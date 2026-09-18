"use client";

import { PanelLeftClose, X } from "lucide-react";

/**
 * Side-panel header: entity-type label + title, collapse/close, and the
 * "From: <message> · Jump to message" strip that ties the panel back to the
 * message that opened it. Collapse is hidden on the mobile sheet.
 */
export function PanelHeader({
  entityLabel,
  title,
  fromMessage,
  onCollapse,
  onClose,
  onJumpToMessage,
  isSheet = false,
}: {
  entityLabel: string;
  title: string;
  fromMessage: string;
  onCollapse?: () => void;
  onClose: () => void;
  onJumpToMessage: () => void;
  isSheet?: boolean;
}) {
  return (
    <>
      <header className="flex h-16 shrink-0 items-center gap-1 border-b border-border-subtle py-0 pr-2 pl-5">
        <div className="flex min-w-0 grow flex-col gap-0.5">
          <span className="text-label-sm text-ink-muted">{entityLabel}</span>
          <h2 className="truncate text-heading-md">{title}</h2>
        </div>
        {isSheet ? null : (
          <button
            type="button"
            aria-label="Collapse panel"
            onClick={onCollapse}
            className="focus-ring flex size-11 items-center justify-center rounded-md text-ink-secondary hover:bg-surface-800"
          >
            <PanelLeftClose className="size-5" aria-hidden />
          </button>
        )}
        <button
          type="button"
          aria-label={isSheet ? "Close sheet" : "Close panel"}
          onClick={onClose}
          className="focus-ring flex size-11 items-center justify-center rounded-md text-ink-secondary hover:bg-surface-800"
        >
          <X className="size-5" aria-hidden />
        </button>
      </header>
      <div className="flex shrink-0 items-center gap-ds-3 border-b border-border-subtle px-ds-5 py-ds-2 text-body-sm">
        <span className="min-w-0 grow truncate text-ink-muted">
          From: <span className="text-ink-secondary">{fromMessage}</span>
        </span>
        <button
          type="button"
          onClick={onJumpToMessage}
          className="focus-ring shrink-0 font-semibold text-accent-live hover:text-accent-live-strong"
        >
          Jump to message
        </button>
      </div>
    </>
  );
}
