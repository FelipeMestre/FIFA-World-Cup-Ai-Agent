import { cn } from "@/lib/utils";

/**
 * Split bar: two teams sharing one match stat (e.g. possession 44/56).
 * Side A (home) is always accent-live, side B (away) always ink-secondary,
 * per design/README.md's series mapping.
 */
export function SplitBarRow({
  label,
  aValue,
  bValue,
  aPct,
  aInkClass,
  bInkClass,
  aBarClass = "bg-accent-live",
  bBarClass = "bg-ink-secondary",
}: {
  label: string;
  aValue: string;
  bValue: string;
  aPct: number;
  aInkClass?: string;
  bInkClass?: string;
  /** Override for a zero-total stat (e.g. 0-0 red cards), per PanelMatch. */
  aBarClass?: string;
  bBarClass?: string;
}) {
  return (
    <div className="flex flex-col gap-ds-2">
      <div className="flex items-center justify-between gap-ds-2">
        <span className={cn("font-mono text-data-md", aInkClass ?? "text-ink-secondary")}>
          {aValue}
        </span>
        <span className="text-label-sm text-ink-muted">{label}</span>
        <span className={cn("font-mono text-data-md", bInkClass ?? "text-ink-primary")}>
          {bValue}
        </span>
      </div>
      <div className="flex h-1.5 gap-0.5">
        <div className={cn("rounded-l-[3px]", aBarClass)} style={{ width: `${aPct}%` }} />
        <div className={cn("grow rounded-r-[3px]", bBarClass)} />
      </div>
    </div>
  );
}

/**
 * Diverging bar: two players compared on one stat, bars growing outward
 * from a center divider. Used in WidgetCompare's "where they differ most".
 */
export function DivergingBarRow({
  label,
  leaderCaption,
  leaderColorClass,
  aValue,
  bValue,
  aPct,
  bPct,
  aInkClass,
  bInkClass,
}: {
  label: string;
  leaderCaption: string;
  leaderColorClass: string;
  aValue: string;
  bValue: string;
  aPct: number;
  bPct: number;
  aInkClass?: string;
  bInkClass?: string;
}) {
  return (
    <div className="flex flex-col gap-ds-2">
      <div className="flex items-center justify-between gap-ds-2">
        <span className="text-body-sm font-medium text-ink-primary">{label}</span>
        <span className={cn("font-mono text-data-sm", leaderColorClass)}>{leaderCaption}</span>
      </div>
      <div className="flex items-center gap-ds-2">
        <span className={cn("w-10 font-mono text-data-md", aInkClass ?? "text-ink-primary")}>
          {aValue}
        </span>
        <div className="flex h-2 flex-1 justify-end rounded-l-md bg-surface-900">
          <div className="rounded-l-md bg-accent-live" style={{ width: `${aPct}%` }} />
        </div>
        <div className="h-3.5 w-px bg-border-strong" />
        <div className="flex h-2 flex-1 rounded-r-md bg-surface-900">
          <div className="rounded-r-md bg-ink-secondary" style={{ width: `${bPct}%` }} />
        </div>
        <span className={cn("w-10 text-right font-mono text-data-md", bInkClass ?? "text-ink-secondary")}>
          {bValue}
        </span>
      </div>
    </div>
  );
}

/** A single ranked-percentile bar, e.g. PanelPlayer's "per 90 vs forward average" chart. */
export function BenchmarkBarRow({
  label,
  value,
  average,
  valuePct,
  averagePct,
}: {
  label: string;
  value: string;
  average: string;
  valuePct: number;
  averagePct: number;
}) {
  return (
    <div className="grid h-8 grid-cols-[104px_1fr_92px] items-center gap-ds-3">
      <span className="text-body-sm text-ink-secondary">{label}</span>
      <div className="relative h-3 rounded-sm bg-surface-800">
        <div
          className="h-3 rounded-sm bg-accent-live"
          style={{ width: `${valuePct}%` }}
        />
        <div
          className="absolute top-[-4px] h-5 w-0.5 bg-data-neutral"
          style={{ left: `${averagePct}%` }}
        />
      </div>
      <span className="text-right font-mono text-data-sm">
        <span className="text-ink-primary">{value}</span>
        <span className="text-ink-muted"> / {average}</span>
      </span>
    </div>
  );
}
