import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const POSITION_LABELS: Record<string, string> = {
  GK: "Goalkeeper",
  DEF: "Defender",
  MID: "Midfielder",
  FWD: "Forward",
};

/** User-facing position text. Stored codes stay GK, DEF, MID, and FWD. */
export function positionLabel(position: string): string {
  return POSITION_LABELS[position] ?? position;
}

const TEAM_CODE_BADGE_LABELS: Record<string, string> = {
  RETIRED: "Retired",
  FREE: "Free agent",
};

/**
 * Player header's team/club indicator. `teamCode` is either a real code
 * (national team or Transfermarkt club name) or one of the sentinels above
 * the backend sends when neither applies (retired, or no current club) --
 * those render as a badge instead of plain text.
 */
export function TeamCodeLabel({ teamCode }: { teamCode: string }) {
  const badgeLabel = TEAM_CODE_BADGE_LABELS[teamCode];
  if (!badgeLabel) {
    return <>{teamCode}</>;
  }
  return <Badge variant="outline">{badgeLabel}</Badge>;
}

/** Solid position tag: Goalkeeper, Defender, Midfielder, Forward. */
export function PositionTag({ position }: { position: string }) {
  return (
    <span className="flex h-6 items-center rounded-sm bg-surface-600 px-ds-2 text-label-sm text-ink-primary">
      {positionLabel(position)}
    </span>
  );
}

/** 3-step contribution meter, filled left-to-right, used inside TierTag. */
function TierMeter({ filled }: { filled: number }) {
  const heights = [6, 8, 10];
  return (
    <span className="flex items-end gap-0.5" aria-hidden>
      {heights.map((h, i) => (
        <span
          key={h}
          className="w-[3px] rounded-[1px]"
          style={{
            height: h,
            background: i < filled ? "var(--color-accent-live)" : "var(--color-border-strong)",
          }}
        />
      ))}
    </span>
  );
}

/** Stats-derived contribution tier, e.g. "G+A tier: elite · top 10%". */
export function TierTag({ label, filled }: { label: string; filled: number }) {
  return (
    <span className="flex h-6 items-center gap-ds-2 rounded-sm border border-border-strong px-ds-2 text-label-sm text-ink-secondary">
      <TierMeter filled={filled} />
      {label}
    </span>
  );
}

/** Discipline tag, e.g. "Discipline: 2 yellows". */
export function DisciplineTag({ label, className }: { label: string; className?: string }) {
  return (
    <span
      className={cn(
        "flex h-6 items-center rounded-sm border border-border-strong px-ds-2 text-label-sm text-ink-secondary",
        className,
      )}
    >
      {label}
    </span>
  );
}
