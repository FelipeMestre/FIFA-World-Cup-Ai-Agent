"use client";

import type { ReactNode } from "react";
import { ArrowUpRight, LayoutDashboard } from "lucide-react";

/**
 * Shared chrome for the four chat widgets (WidgetTeam/Match/Player/Compare):
 * a header strip (icon + label, scope caption), the caller's own body zones,
 * and a footer action -- "View full details" normally, or "Showing in
 * panel" (with a live dot) when this widget's entity is the one currently
 * pinned in the side panel. 640px on desktop, full width on mobile.
 */
export function WidgetFrame({
  icon,
  label,
  scopeText,
  footerCaption,
  active,
  onViewDetails,
  ariaLabel,
  children,
}: {
  icon: ReactNode;
  label: string;
  scopeText: string;
  footerCaption: string;
  active: boolean;
  onViewDetails: () => void;
  ariaLabel: string;
  children: ReactNode;
}) {
  return (
    <article
      aria-label={ariaLabel}
      className="flex w-full max-w-[640px] flex-col overflow-hidden rounded-lg border border-border-strong bg-surface-800 text-ink-primary"
    >
      <div className="flex h-10 shrink-0 items-center justify-between gap-ds-3 border-b border-border-subtle px-ds-4">
        <div className="flex items-center gap-ds-2 text-ink-secondary">
          {icon}
          <span className="text-label-sm text-ink-muted">{label}</span>
        </div>
        <span className="font-mono text-data-sm text-ink-muted">{scopeText}</span>
      </div>

      {children}

      <div className="flex shrink-0 items-center justify-between gap-ds-3 border-t border-border-subtle px-ds-4 py-ds-3">
        <span className="text-body-sm text-ink-muted">{footerCaption}</span>
        {active ? (
          <button
            type="button"
            aria-pressed="true"
            onClick={onViewDetails}
            className="focus-ring flex h-11 items-center gap-ds-2 rounded-md border border-border-strong bg-surface-600 px-[14px] text-label-md text-ink-primary"
          >
            <span className="size-1.5 rounded-full bg-accent-live" />
            Showing in panel
            <LayoutDashboard className="size-4" aria-hidden />
          </button>
        ) : (
          <button
            type="button"
            onClick={onViewDetails}
            className="focus-ring flex h-11 items-center gap-ds-2 rounded-md border border-border-strong bg-transparent px-[14px] text-label-md text-ink-primary hover:bg-surface-700"
          >
            View full details
            <ArrowUpRight className="size-4" aria-hidden />
          </button>
        )}
      </div>
    </article>
  );
}
