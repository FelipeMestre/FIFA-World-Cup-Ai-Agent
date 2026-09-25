"use client";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { StatChip } from "@/features/chat/components/stat-chip";
import {
  formatAge,
  formatCount,
  formatMarketValue,
  formatRecord,
} from "@/features/chat/format-team-comparison";
import type { ComparedTeam, SquadLeader } from "@/features/chat/team-comparison";

const PIE_RADIUS = 16;
const PIE_CIRCUMFERENCE = 2 * Math.PI * PIE_RADIUS;

function dash(value: number | null): string {
  return value == null ? "—" : String(value);
}

function AgeMixChart({ under23, over30 }: { under23: number; over30: number }) {
  const remainder = Math.max(0, 100 - under23 - over30);
  const slices = [
    { label: "Under 23", value: under23, color: "var(--color-accent-live)" },
    { label: "23–30", value: remainder, color: "var(--color-ink-secondary)" },
    { label: "Over 30", value: over30, color: "var(--color-brand)" },
  ];
  let offset = 0;

  return (
    <div className="flex items-center gap-ds-4">
      <svg viewBox="0 0 40 40" className="size-16 shrink-0" aria-hidden>
        {slices.map((slice) => {
          const length = (slice.value / 100) * PIE_CIRCUMFERENCE;
          const dashoffset = -offset;
          offset += length;
          return (
            <circle
              key={slice.label}
              cx="20"
              cy="20"
              r={PIE_RADIUS}
              fill="none"
              stroke={slice.color}
              strokeWidth="8"
              strokeDasharray={`${length} ${PIE_CIRCUMFERENCE - length}`}
              strokeDashoffset={dashoffset}
              transform="rotate(-90 20 20)"
            />
          );
        })}
      </svg>
      <ul className="flex flex-col gap-ds-1">
        {slices.map((slice) => (
          <li key={slice.label} className="flex items-center gap-ds-2 text-body-sm">
            <span
              className={
                slice.label === "Under 23"
                  ? "size-2 shrink-0 rounded-full bg-accent-live"
                  : slice.label === "Over 30"
                    ? "size-2 shrink-0 rounded-full bg-brand"
                    : "size-2 shrink-0 rounded-full bg-ink-secondary"
              }
            />
            <span className="text-ink-muted">{slice.label}</span>
            <span className="font-mono text-data-sm text-ink-primary">{slice.value.toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LeaderRow({
  label,
  leader,
  figure,
}: {
  label: string;
  leader: SquadLeader | null;
  figure: (leader: SquadLeader) => string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-ds-3 border-b border-border-subtle py-ds-2 last:border-b-0">
      <span className="text-label-sm text-ink-muted">{label}</span>
      {leader ? (
        <span className="min-w-0 text-right">
          <span className="block truncate text-body-md text-ink-primary">{leader.name}</span>
          <span className="font-mono text-data-sm text-ink-secondary">{figure(leader)}</span>
        </span>
      ) : (
        <span className="text-body-sm text-ink-muted">—</span>
      )}
    </div>
  );
}

export function TeamCompareIdentity({ team }: { team: ComparedTeam }) {
  const { squad } = team;

  return (
    <div className="flex flex-col gap-ds-4">
      <div className="flex items-center gap-ds-3">
        <AvatarBadge label={team.code} size={48} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-heading-md">{team.name}</span>
          <span className="text-body-sm text-ink-secondary">{team.standingLabel}</span>
        </div>
        <span className="ml-auto font-mono text-data-lg">{formatRecord(team.record)}</span>
      </div>

      <div className="grid grid-cols-3 gap-ds-2">
        <StatChip variant="tile" label="Age" value={formatAge(squad.averageAge)} />
        <StatChip variant="tile" label="Value" value={formatMarketValue(squad.totalMarketValueEur)} />
        <StatChip variant="tile" label="Group pts" value={String(team.group.points)} />
        <StatChip variant="tile" label="FIFA rank" value={dash(team.fifaRankingPreTournament)} />
        <StatChip variant="tile" label="Manager" value={team.managerName ?? "—"} />
        <StatChip variant="tile" label="Confederation" value={team.confederation} />
      </div>

      <div className="grid grid-cols-2 gap-ds-3">
        <div className="flex flex-col gap-ds-2 rounded-lg border border-border-strong bg-surface-800 p-ds-3">
          <span className="text-label-sm text-ink-muted">Age mix · {squad.rosterSize} players</span>
          <AgeMixChart under23={squad.under23Pct} over30={squad.over30Pct} />
          <span className="text-body-sm text-ink-muted">
            Youngest {dash(squad.youngestAge)} · oldest {dash(squad.oldestAge)}
          </span>
        </div>
        <div className="flex flex-col overflow-hidden rounded-lg border border-border-strong bg-surface-800">
          <div className="flex items-center gap-ds-1 border-b border-border-subtle px-ds-3 py-ds-2 justify-center">
            <span className="text-label-sm text-ink-muted">Group</span>
            <span className="font-mono text-data-md">{team.groupLetter ?? "—"}</span>
          </div>
          <div className="flex flex-col gap-ds-1 p-ds-3">
            <span className="text-label-sm text-ink-muted">Squad value</span>
            <span className="font-mono text-data-lg">{formatMarketValue(squad.totalMarketValueEur)}</span>
            <span className="text-body-sm text-ink-secondary">
              Top 3 hold {squad.topThreeValueSharePct.toFixed(1)}% of the roster
            </span>
            {squad.transfermarktMarketValueEur != null || squad.transfermarktAverageAge != null ? (
              <span className="text-body-sm text-ink-muted">
                Transfermarkt {formatMarketValue(squad.transfermarktMarketValueEur)} · age{" "}
                {formatAge(squad.transfermarktAverageAge)} · {formatCount(squad.transfermarktSquadSize)} listed
              </span>
            ) : null}
          </div>
        </div>
      </div>

      <div className="flex flex-col rounded-lg border border-border-strong bg-surface-800 px-ds-3">
        <div className="flex items-baseline justify-between gap-ds-3 border-b border-border-subtle py-ds-2">
          <span className="text-label-sm text-ink-muted">Starters</span>
          <span className="font-mono text-data-md">{squad.distinctStarters}</span>
        </div>
        <div className="flex items-baseline justify-between gap-ds-3 border-b border-border-subtle py-ds-2">
          <span className="text-label-sm text-ink-muted">Starter minutes</span>
          <span className="font-mono text-data-md">{squad.starterMinutesSharePct.toFixed(1)}%</span>
        </div>
        <LeaderRow label="Top scorer" leader={team.topScorer} figure={(row) => `${row.goals} goals`} />
        <LeaderRow label="Top assister" leader={team.topAssister} figure={(row) => `${row.assists} assists`} />
        <LeaderRow label="Most minutes" leader={team.mostMinutes} figure={(row) => `${row.minutes} min`} />
      </div>
    </div>
  );
}
