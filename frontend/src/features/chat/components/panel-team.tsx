"use client";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { PanelHeader } from "@/features/chat/components/panel-header";
import { ResultPill } from "@/features/chat/components/result-pill";
import { StatChip } from "@/features/chat/components/stat-chip";
import type { TeamSummary } from "@/features/chat/types";

/** Team detail side panel (design/artboards/PanelTeam.dc.html). */
export function PanelTeam({
  team,
  fromMessage,
  onCollapse,
  onClose,
  onJumpToMessage,
  isSheet = false,
}: {
  team: TeamSummary;
  fromMessage: string;
  onCollapse?: () => void;
  onClose: () => void;
  onJumpToMessage: () => void;
  isSheet?: boolean;
}) {
  const { record } = team;
  const recordTiles = [
    { label: "Won", value: String(record.won), className: "text-data-positive" },
    { label: "Drawn", value: String(record.drawn), className: "text-data-neutral" },
    { label: "Lost", value: String(record.lost), className: "text-data-negative" },
    { label: "Goals for", value: String(record.goalsFor), className: "text-ink-primary" },
    { label: "Against", value: String(record.goalsAgainst), className: "text-ink-primary" },
    {
      label: "Goal diff",
      value: `${team.goalDifference >= 0 ? "▲ +" : "▼ "}${Math.abs(team.goalDifference)}`,
      className: team.goalDifference >= 0 ? "text-data-positive" : "text-data-negative",
    },
  ];

  return (
    <aside aria-label={`Team detail: ${team.name}`} className="flex h-full flex-col bg-surface-900">
      <PanelHeader
        entityLabel="Team detail"
        title={team.name}
        fromMessage={fromMessage}
        onCollapse={onCollapse}
        onClose={onClose}
        onJumpToMessage={onJumpToMessage}
        isSheet={isSheet}
      />

      <section className="flex shrink-0 flex-col gap-4 border-b border-border-subtle p-5">
        <div className="flex items-center gap-3.5">
          <AvatarBadge label={team.code} size={56} className="text-heading-md" />
          <div className="flex flex-col gap-0.5">
            <span className="text-heading-lg">{team.name}</span>
            <span className="text-body-sm text-ink-secondary">{team.scopeLabel}</span>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {recordTiles.map((tile) => (
            <StatChip
              key={tile.label}
              variant="tile"
              label={tile.label}
              value={tile.value}
              valueClassName={tile.className}
            />
          ))}
        </div>
      </section>

      <section className="flex shrink-0 flex-col gap-3 border-b border-border-subtle p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-heading-sm">Tournament averages</h3>
          <span className="text-label-sm text-ink-muted">Per match · vs field</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {team.tournamentAverages.map((row) => (
            <StatChip
              key={row.label}
              variant="tile"
              label={row.label}
              value={row.value}
              secondary={{ fieldLabel: row.fieldValue, delta: row.delta }}
            />
          ))}
        </div>
      </section>

      <section className="flex shrink-0 flex-col gap-3 border-b border-border-subtle p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-heading-sm">Match by match</h3>
          <span className="text-label-sm text-ink-muted">{team.matchResults.length} played</span>
        </div>
        <div className="flex flex-col">
          {team.matchResults.map((row) => (
            <div
              key={`${row.stage}-${row.opponentCode}`}
              className="flex h-12 items-center gap-3 border-b border-border-subtle"
            >
              <span className="w-8 text-label-sm text-ink-muted">{row.stage}</span>
              <AvatarBadge label={row.opponentCode} size={28} className="text-[9px]" />
              <span className="grow text-body-md">{row.opponentName}</span>
              <span className="font-mono text-data-md">{row.score}</span>
              <ResultPill result={row.result} />
            </div>
          ))}
        </div>
      </section>

      <section className="flex grow flex-col gap-3 p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-heading-sm">Discipline</h3>
          <span className="text-label-sm text-ink-muted">Totals</span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          <StatChip variant="tile" label="Yellow cards" value={String(team.discipline.yellowCards)} />
          <StatChip variant="tile" label="Red cards" value={String(team.discipline.redCards)} />
          <StatChip variant="tile" label="Fouls" value={String(team.discipline.fouls)} />
        </div>
        <span className="text-body-sm text-ink-muted">
          {team.discipline.yellowPerMatch.toFixed(2)} yellow cards per match · field{" "}
          {team.discipline.fieldYellowPerMatch.toFixed(2)}
        </span>
      </section>
    </aside>
  );
}
