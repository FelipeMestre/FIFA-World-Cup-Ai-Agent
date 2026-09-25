"use client";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { SplitBarRow } from "@/features/chat/components/comparison-row";
import { PanelHeader } from "@/features/chat/components/panel-header";
import { ResultPill } from "@/features/chat/components/result-pill";
import { StatChip } from "@/features/chat/components/stat-chip";
import { TeamComparePositions } from "@/features/chat/components/team-compare-positions";
import {
  barShare,
  formatAge,
  formatCount,
  formatMarketValue,
  formatRecord,
} from "@/features/chat/format-team-comparison";
import type { ComparedTeam, TeamComparison } from "@/features/chat/team-comparison";

function dash(value: number | null): string {
  return value == null ? "—" : String(value);
}

function TeamIdentity({ team }: { team: ComparedTeam }) {
  return (
    <div className="flex flex-col gap-ds-3">
      <div className="flex items-center gap-ds-3">
        <AvatarBadge label={team.code} size={48} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-heading-md">{team.name}</span>
          <span className="text-body-sm text-ink-secondary">{team.standingLabel}</span>
        </div>
        <span className="ml-auto font-mono text-data-lg">{formatRecord(team.record)}</span>
      </div>
      <div className="grid grid-cols-3 gap-ds-2">
        <StatChip variant="tile" label="Age" value={formatAge(team.squad.averageAge)} />
        <StatChip variant="tile" label="Value" value={formatMarketValue(team.squad.totalMarketValueEur)} />
        <StatChip variant="tile" label="Group pts" value={String(team.group.points)} />
        <StatChip variant="tile" label="FIFA rank" value={dash(team.fifaRankingPreTournament)} />
        <StatChip variant="tile" label="Elo" value={dash(team.eloRating)} />
        <StatChip variant="tile" label="Manager" value={team.managerName ?? "—"} />
      </div>
      <span className="text-body-sm text-ink-muted">
        {team.confederation}
        {team.groupLetter ? ` · Group ${team.groupLetter}` : ""} · {team.squad.rosterSize} players ·{" "}
        {team.squad.under23Pct.toFixed(1)}% under 23 · {team.squad.over30Pct.toFixed(1)}% over 30 · top 3 hold{" "}
        {team.squad.topThreeValueSharePct.toFixed(1)}% of the value · {team.squad.distinctStarters} starters ·{" "}
        {team.squad.starterMinutesSharePct.toFixed(1)}% of minutes
      </span>
      {team.squad.transfermarktMarketValueEur != null || team.squad.transfermarktAverageAge != null ? (
        <span className="text-body-sm text-ink-muted">
          Transfermarkt squad {formatMarketValue(team.squad.transfermarktMarketValueEur)} · age{" "}
          {formatAge(team.squad.transfermarktAverageAge)} · {formatCount(team.squad.transfermarktSquadSize)} listed
        </span>
      ) : null}
      <span className="text-body-sm text-ink-secondary">
        {team.topScorer ? `Top scorer ${team.topScorer.name} (${team.topScorer.goals})` : "No scorer"}
        {" · "}
        {team.topAssister ? `Top assister ${team.topAssister.name} (${team.topAssister.assists})` : "No assister"}
        {" · "}
        {team.mostMinutes ? `Most minutes ${team.mostMinutes.name} (${team.mostMinutes.minutes})` : "No minutes"}
      </span>
    </div>
  );
}

/** Team comparison detail. Position groups are the player-by-player view. */
export function PanelTeamCompare({
  comparison,
  fromMessage,
  onClose,
  onJumpToMessage,
  isSheet = false,
}: {
  comparison: TeamComparison;
  fromMessage: string;
  onClose: () => void;
  onJumpToMessage: () => void;
  isSheet?: boolean;
}) {
  const { teamA, teamB } = comparison;

  return (
    <aside
      aria-label={`Team comparison: ${teamA.name} and ${teamB.name}`}
      className="flex h-full flex-col bg-surface-900"
    >
      <PanelHeader
        entityLabel="Team comparison"
        title={`${teamA.name} vs ${teamB.name}`}
        fromMessage={fromMessage}
        onClose={onClose}
        onJumpToMessage={onJumpToMessage}
        isSheet={isSheet}
      />

      <section className="flex flex-col gap-ds-5 border-b border-border-subtle p-ds-5">
        <TeamIdentity team={teamA} />
        <TeamIdentity team={teamB} />
      </section>

      <section className="flex flex-col gap-ds-3 border-b border-border-subtle p-ds-5">
        <h3 className="text-heading-sm">Strengths and flaws</h3>
        {comparison.strengthsAndFlaws.length === 0 ? (
          <span className="text-body-sm text-ink-muted">No gap cleared the tournament average.</span>
        ) : (
          comparison.strengthsAndFlaws.map((note) => {
            const team = note.side === "a" ? teamA : teamB;
            return (
              <div key={`${note.side}-${note.kind}-${note.label}`} className="flex flex-col gap-0.5">
                <span
                  className={
                    note.kind === "strength"
                      ? "text-label-sm text-data-positive"
                      : "text-label-sm text-data-negative"
                  }
                >
                  {note.kind === "strength" ? "▲" : "▼"} {team.code} · {note.label}
                </span>
                <span className="text-body-sm text-ink-secondary">{note.detail}</span>
              </div>
            );
          })
        )}
      </section>

      <section className="flex flex-col gap-ds-3 border-b border-border-subtle p-ds-5">
        <div className="flex items-baseline justify-between gap-ds-3">
          <h3 className="text-heading-sm">Match stats</h3>
          <span className="text-label-sm text-ink-muted">vs field</span>
        </div>
        {comparison.comparedStats.map((stat) => (
          <div key={stat.label} className="flex flex-col gap-ds-1">
            <SplitBarRow
              label={stat.label}
              aValue={stat.teamADisplay}
              bValue={stat.teamBDisplay}
              aPct={barShare(stat)}
              aInkClass={stat.teamAIsBetter ? "text-ink-primary" : "text-ink-secondary"}
              bInkClass={stat.teamBIsBetter ? "text-ink-primary" : "text-ink-secondary"}
            />
            <span className="text-body-sm text-ink-muted">Field {stat.fieldDisplay}</span>
          </div>
        ))}
      </section>

      <section className="flex flex-col gap-ds-3 border-b border-border-subtle p-ds-5">
        <h3 className="text-heading-sm">Results</h3>
        {[teamA, teamB].map((team) => (
          <div key={team.id} className="flex flex-col">
            <span className="text-label-sm text-ink-muted">{team.code}</span>
            {team.matchResults.map((row) => (
              <div
                key={`${team.id}-${row.stage}-${row.opponentCode}`}
                className="flex h-12 items-center gap-ds-3 border-b border-border-subtle"
              >
                <span className="w-10 text-label-sm text-ink-muted">{row.stage}</span>
                <span className="grow text-body-md">{row.opponentName}</span>
                <span className="font-mono text-data-md">{row.score}</span>
                <ResultPill result={row.result} />
              </div>
            ))}
          </div>
        ))}
      </section>

      <section className="flex flex-col gap-ds-3 border-b border-border-subtle p-ds-5">
        <h3 className="text-heading-sm">Discipline</h3>
        <div className="grid grid-cols-2 gap-ds-2">
          <StatChip variant="tile" label={`${teamA.code} yellows`} value={String(teamA.discipline.yellowCards)} />
          <StatChip variant="tile" label={`${teamB.code} yellows`} value={String(teamB.discipline.yellowCards)} />
          <StatChip variant="tile" label={`${teamA.code} reds`} value={String(teamA.discipline.redCards)} />
          <StatChip variant="tile" label={`${teamB.code} reds`} value={String(teamB.discipline.redCards)} />
        </div>
        <span className="text-body-sm text-ink-muted">
          {teamA.code} {teamA.discipline.yellowPerMatch.toFixed(2)} yellows per match · {teamB.code}{" "}
          {teamB.discipline.yellowPerMatch.toFixed(2)} · {teamA.code} {teamA.discipline.fouls} fouls · {teamB.code}{" "}
          {teamB.discipline.fouls}
        </span>
      </section>

      <TeamComparePositions teamACode={teamA.code} teamBCode={teamB.code} positions={comparison.positions} />
    </aside>
  );
}
