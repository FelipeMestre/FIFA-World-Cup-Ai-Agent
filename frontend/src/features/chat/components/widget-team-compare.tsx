"use client";

import { Swords } from "lucide-react";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { SplitBarRow } from "@/features/chat/components/comparison-row";
import { ResultPill } from "@/features/chat/components/result-pill";
import { StatChip } from "@/features/chat/components/stat-chip";
import { WidgetFrame } from "@/features/chat/components/widget-frame";
import {
  barShare,
  formatAge,
  formatMarketValue,
  formatRecord,
} from "@/features/chat/format-team-comparison";
import type { ComparedStat, ComparedTeam, SideNote, TeamComparison } from "@/features/chat/team-comparison";

const HEADLINE_STATS = [
  "Possession",
  "Goals per game",
  "Goals conceded / game",
  "xG difference / game",
];

function sideInk(isBetter: boolean): string {
  return isBetter ? "text-ink-primary" : "text-ink-secondary";
}

function TeamHead({ team, align }: { team: ComparedTeam; align: "start" | "end" }) {
  const end = align === "end";
  return (
    <div className={`flex flex-col gap-1 ${end ? "items-end text-right" : "items-start"}`}>
      <AvatarBadge
        label={team.code}
        size={40}
        seriesColor={end ? "var(--color-ink-secondary)" : "var(--color-accent-live)"}
      />
      <span className="text-heading-md">{team.name}</span>
      <span className="text-body-sm text-ink-secondary">{team.standingLabel}</span>
      <span className="font-mono text-data-md">{formatRecord(team.record)}</span>
    </div>
  );
}

function NoteList({ notes }: { notes: SideNote[] }) {
  if (notes.length === 0) {
    return <span className="text-body-sm text-ink-muted">No gap cleared the field</span>;
  }
  return (
    <ul className="flex flex-col gap-ds-2">
      {notes.map((note) => (
        <li key={`${note.kind}-${note.label}`} className="flex flex-col gap-0.5">
          <span
            className={
              note.kind === "strength"
                ? "text-label-sm text-data-positive"
                : "text-label-sm text-data-negative"
            }
          >
            {note.kind === "strength" ? "▲" : "▼"} {note.label}
          </span>
          <span className="text-body-sm text-ink-secondary">{note.detail}</span>
        </li>
      ))}
    </ul>
  );
}

/** Team comparison widget. The position-by-position squad lives in the panel. */
export function WidgetTeamCompare({
  comparison,
  active,
  onViewDetails,
}: {
  comparison: TeamComparison;
  active: boolean;
  onViewDetails: () => void;
}) {
  const { teamA, teamB } = comparison;
  const headline = HEADLINE_STATS.map((label) =>
    comparison.comparedStats.find((stat) => stat.label === label),
  ).filter((stat): stat is ComparedStat => stat != null);
  const footer =
    teamA.stageCaption === teamB.stageCaption
      ? teamA.stageCaption
      : `${teamA.code} ${teamA.stageCaption} · ${teamB.code} ${teamB.stageCaption}`;

  return (
    <WidgetFrame
      ariaLabel={`Team comparison: ${teamA.name} and ${teamB.name}`}
      icon={<Swords className="size-4" aria-hidden />}
      label="Team comparison"
      scopeText={comparison.scopeLabel}
      footerCaption={footer}
      active={active}
      onViewDetails={onViewDetails}
    >
      <div className="grid shrink-0 grid-cols-[1fr_auto_1fr] items-start gap-ds-3 border-b border-border-subtle p-ds-4">
        <TeamHead team={teamA} align="start" />
        <span className="pt-3 text-label-sm text-ink-muted">vs</span>
        <TeamHead team={teamB} align="end" />
      </div>

      <div className="grid shrink-0 grid-cols-2 gap-ds-2 px-ds-4 pt-ds-3 sm:grid-cols-4">
        <StatChip label={`${teamA.code} age`} value={formatAge(teamA.squad.averageAge)} />
        <StatChip label={`${teamA.code} value`} value={formatMarketValue(teamA.squad.totalMarketValueEur)} />
        <StatChip label={`${teamB.code} value`} value={formatMarketValue(teamB.squad.totalMarketValueEur)} />
        <StatChip label={`${teamB.code} age`} value={formatAge(teamB.squad.averageAge)} />
      </div>

      {comparison.meetings.length > 0 ? (
        <div className="flex shrink-0 flex-col gap-ds-2 px-ds-4 pt-ds-3">
          <span className="text-label-sm text-ink-muted">When they met</span>
          {comparison.meetings.map((meeting) => (
            <div key={meeting.matchId} className="flex items-center gap-ds-3">
              <span className="w-16 text-label-sm text-ink-muted">{meeting.stage}</span>
              <span className="font-mono text-data-md">
                {meeting.teamAScore}–{meeting.teamBScore}
              </span>
              <ResultPill result={meeting.teamAResult} />
              {meeting.penaltyScore ? (
                <span className="text-body-sm text-ink-secondary">pens {meeting.penaltyScore}</span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="flex grow flex-col gap-ds-4 p-ds-4">
        <div className="flex flex-col gap-ds-3">
          {headline.map((stat) => (
            <SplitBarRow
              key={stat.label}
              label={stat.label}
              aValue={stat.teamADisplay}
              bValue={stat.teamBDisplay}
              aPct={barShare(stat)}
              aInkClass={sideInk(stat.teamAIsBetter)}
              bInkClass={sideInk(stat.teamBIsBetter)}
            />
          ))}
        </div>
        <div className="grid grid-cols-2 gap-ds-4 border-t border-border-subtle pt-ds-3">
          <div className="flex flex-col gap-ds-2">
            <span className="text-label-sm text-ink-muted">{teamA.code}</span>
            <NoteList notes={comparison.strengthsAndFlaws.filter((note) => note.side === "a")} />
          </div>
          <div className="flex flex-col gap-ds-2">
            <span className="text-label-sm text-ink-muted">{teamB.code}</span>
            <NoteList notes={comparison.strengthsAndFlaws.filter((note) => note.side === "b")} />
          </div>
        </div>
      </div>
    </WidgetFrame>
  );
}
