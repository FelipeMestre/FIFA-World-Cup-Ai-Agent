"use client";

import { Shield } from "lucide-react";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { StatChip } from "@/features/chat/components/stat-chip";
import { WidgetFrame } from "@/features/chat/components/widget-frame";
import { formatAge, formatMarketValue } from "@/features/chat/format-team-comparison";
import type { TeamSummary } from "@/features/chat/types";

const BAR_UNIT_PX = 14;

/** Team analysis widget (design/artboards/WidgetTeam.dc.html). */
export function WidgetTeam({
  team,
  active,
  onViewDetails,
}: {
  team: TeamSummary;
  active: boolean;
  onViewDetails: () => void;
}) {
  const record = `${team.record.won}–${team.record.drawn}–${team.record.lost}`;
  const goalDiffLabel = `${team.goalDifference >= 0 ? "▲ +" : "▼ "}${Math.abs(team.goalDifference)}`;

  return (
    <WidgetFrame
      ariaLabel={`Team analysis: ${team.name}`}
      icon={<Shield className="size-4" aria-hidden />}
      label="Team analysis"
      scopeText={team.scopeLabel}
      footerCaption={team.stageCaption}
      active={active}
      onViewDetails={onViewDetails}
    >
      <div className="flex shrink-0 items-center gap-ds-3 px-ds-4 pt-ds-4 pb-ds-3">
        <AvatarBadge label={team.code} size={48} />
        <div className="flex min-w-0 grow flex-col gap-0.5">
          <span className="text-heading-md">{team.name}</span>
          <span className="text-body-sm text-ink-secondary">{team.standingLabel}</span>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <span className="font-mono text-data-lg">{record}</span>
          <span className="text-label-sm text-ink-muted">W–D–L</span>
        </div>
      </div>

      <div className="grid shrink-0 grid-cols-2 gap-ds-2 px-ds-4 sm:grid-cols-3">
        <StatChip label="Age" value={formatAge(team.squad.averageAge)} />
        <StatChip label="Value" value={formatMarketValue(team.squad.totalMarketValueEur)} />
        <StatChip
          label="Goal diff"
          value={goalDiffLabel}
          valueClassName={team.goalDifference >= 0 ? "text-data-positive" : "text-data-negative"}
        />
        <StatChip label="Conceded / game" value={team.concededPerGame.toFixed(2)} />
        <StatChip label="Clean sheets" value={String(team.cleanSheets)} />
        <StatChip label="Avg possession" value={`${team.avgPossessionPct.toFixed(1)}%`} />
      </div>

      <div className="flex grow flex-col gap-ds-3 p-ds-4">
        <div className="flex flex-wrap items-center justify-between gap-ds-3">
          <span className="text-label-sm text-ink-muted">Goals for vs against, by match</span>
          <div className="flex gap-ds-3 text-body-sm text-ink-secondary">
            <span className="flex items-center gap-ds-1">
              <span className="size-2 rounded-[2px] bg-data-positive" />▲ For
            </span>
            <span className="flex items-center gap-ds-1">
              <span className="size-2 rounded-[2px] bg-data-negative" />▼ Against
            </span>
          </div>
        </div>
        <div className="flex gap-ds-1">
          {team.goalsByMatch.map((m) => (
            <div key={m.opponentCode} className="flex min-w-0 flex-1 flex-col items-center">
              <div className="flex h-16 flex-col items-center justify-end gap-1">
                <span className="font-mono text-data-sm text-data-positive">{m.goalsFor}</span>
                <div
                  className="w-4 rounded-t-sm bg-data-positive"
                  style={{ height: m.goalsFor * BAR_UNIT_PX }}
                />
              </div>
              <div className="h-px w-full bg-border-strong" />
              <div className="flex h-[50px] flex-col items-center justify-start gap-1">
                <div
                  className="w-4 rounded-b-sm bg-data-negative"
                  style={{ height: m.goalsAgainst * BAR_UNIT_PX }}
                />
                <span className="font-mono text-data-sm text-data-negative">{m.goalsAgainst}</span>
              </div>
              <span className="mt-1 font-mono text-data-sm text-ink-muted">{m.opponentCode}</span>
            </div>
          ))}
        </div>
      </div>
    </WidgetFrame>
  );
}
