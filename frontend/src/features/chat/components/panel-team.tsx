"use client";

import { PanelHeader } from "@/features/chat/components/panel-header";
import { ResultPill } from "@/features/chat/components/result-pill";
import { StatChip } from "@/features/chat/components/stat-chip";
import { TeamCompareIdentity } from "@/features/chat/components/team-compare-identity";
import { TeamPositionSquads } from "@/features/chat/components/team-compare-positions";
import type { TeamSummary } from "@/features/chat/types";

/** Team detail side panel (design/artboards/PanelTeam.dc.html). */
export function PanelTeam({
  team,
  fromMessage,
  onClose,
  onJumpToMessage,
  isSheet = false,
}: {
  team: TeamSummary;
  fromMessage: string;
  onClose: () => void;
  onJumpToMessage: () => void;
  isSheet?: boolean;
}) {
  return (
    <aside
      aria-label={`Team detail: ${team.name}`}
      className="flex h-full flex-col bg-surface-900"
    >
      <PanelHeader
        entityLabel="Team detail"
        title={team.name}
        fromMessage={fromMessage}
        onClose={onClose}
        onJumpToMessage={onJumpToMessage}
        isSheet={isSheet}
      />

      <section className="flex shrink-0 flex-col gap-ds-4 border-b border-border-subtle p-ds-5">
        <TeamCompareIdentity team={team} />
      </section>

      <section className="flex shrink-0 flex-col gap-ds-3 border-b border-border-subtle p-ds-5">
        <div className="flex items-baseline justify-between gap-ds-3">
          <h3 className="text-heading-sm">Tournament averages</h3>
          <span className="text-label-sm text-ink-muted">Per match · vs field</span>
        </div>
        <div className="grid grid-cols-2 gap-ds-2">
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

      <section className="flex shrink-0 flex-col gap-ds-3 border-b border-border-subtle p-ds-5">
        <div className="flex items-baseline justify-between gap-ds-3">
          <h3 className="text-heading-sm">Match by match</h3>
          <span className="text-label-sm text-ink-muted">{team.matchResults.length} played</span>
        </div>
        <div className="flex flex-col">
          {team.matchResults.map((row) => (
            <div
              key={`${row.stage}-${row.opponentCode}`}
              className="flex h-12 items-center gap-ds-3 border-b border-border-subtle"
            >
              <span className="w-8 text-label-sm text-ink-muted">{row.stage}</span>
              <span className="grow text-body-md">{row.opponentName}</span>
              <span className="font-mono text-data-md">{row.score}</span>
              <ResultPill result={row.result} />
            </div>
          ))}
        </div>
      </section>

      <section className="flex shrink-0 flex-col gap-ds-3 border-b border-border-subtle p-ds-5">
        <div className="flex items-baseline justify-between gap-ds-3">
          <h3 className="text-heading-sm">Discipline</h3>
          <span className="text-label-sm text-ink-muted">Totals</span>
        </div>
        <div className="grid grid-cols-3 gap-ds-2">
          <StatChip variant="tile" label="Yellow cards" value={String(team.discipline.yellowCards)} />
          <StatChip variant="tile" label="Red cards" value={String(team.discipline.redCards)} />
          <StatChip variant="tile" label="Fouls" value={String(team.discipline.fouls)} />
        </div>
        <span className="text-body-sm text-ink-muted">
          {team.discipline.yellowPerMatch.toFixed(2)} yellow cards per match · field{" "}
          {team.discipline.fieldYellowPerMatch.toFixed(2)}
        </span>
      </section>

      <TeamPositionSquads code={team.code} positions={team.positions} />
    </aside>
  );
}
