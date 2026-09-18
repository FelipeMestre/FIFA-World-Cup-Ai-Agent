"use client";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { SplitBarRow } from "@/features/chat/components/comparison-row";
import { PanelHeader } from "@/features/chat/components/panel-header";
import { TimelineItem } from "@/features/chat/components/timeline-item";
import type { MatchSummary } from "@/features/chat/types";

/** Match detail side panel (design/artboards/PanelMatch.dc.html). */
export function PanelMatch({
  match,
  fromMessage,
  onCollapse,
  onClose,
  onJumpToMessage,
  isSheet = false,
}: {
  match: MatchSummary;
  fromMessage: string;
  onCollapse?: () => void;
  onClose: () => void;
  onJumpToMessage: () => void;
  isSheet?: boolean;
}) {
  return (
    <aside
      aria-label={`Match detail: ${match.homeTeam.name} ${match.homeScore}, ${match.awayTeam.name} ${match.awayScore}`}
      className="flex h-full flex-col bg-surface-900"
    >
      <PanelHeader
        entityLabel="Match detail"
        title={`${match.homeTeam.name} ${match.homeScore}–${match.awayScore} ${match.awayTeam.name}`}
        fromMessage={fromMessage}
        onCollapse={onCollapse}
        onClose={onClose}
        onJumpToMessage={onJumpToMessage}
        isSheet={isSheet}
      />

      <section className="flex shrink-0 flex-col gap-3.5 border-b border-border-subtle p-5">
        <span className="text-center text-label-sm text-ink-muted">
          {match.stageLabel} · {match.dateLabel} · {match.venueLabel ?? "[VENUE]"}
        </span>
        <div className="grid grid-cols-[1fr_auto_1fr] items-start gap-3">
          <div className="flex flex-col items-center gap-1.5 text-center">
            <AvatarBadge label={match.homeTeam.code} size={48} />
            <span className="text-heading-sm">{match.homeTeam.name}</span>
            <span className="h-[3px] w-5 rounded-sm bg-accent-live" />
            <span className="text-body-sm text-ink-secondary">{match.homeScorers}</span>
          </div>
          <div className="flex flex-col items-center gap-1 pt-1">
            <div className="flex items-center gap-3 font-mono text-data-xl">
              <span className="text-ink-secondary">{match.homeScore}</span>
              <span className="text-[24px] text-ink-muted">–</span>
              <span>{match.awayScore}</span>
            </div>
            <span className="text-label-sm text-ink-muted">{match.statusLabel}</span>
          </div>
          <div className="flex flex-col items-center gap-1.5 text-center">
            <AvatarBadge label={match.awayTeam.code} size={48} />
            <span className="text-heading-sm">{match.awayTeam.name}</span>
            <span className="h-[3px] w-5 rounded-sm bg-ink-secondary" />
            <span className="text-body-sm text-ink-secondary">{match.awayScorers}</span>
          </div>
        </div>
      </section>

      <section className="flex shrink-0 flex-col gap-3 border-b border-border-subtle p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-heading-sm">Team stats</h3>
          <span className="text-label-sm text-ink-muted">
            {match.homeTeam.code} · {match.awayTeam.code}
          </span>
        </div>
        {match.stats.map((row) => {
          const total = Number(row.homeValue) + Number(row.awayValue);
          const isZero = Number.isFinite(total) && total === 0;
          return (
            <SplitBarRow
              key={row.label}
              label={row.label}
              aValue={row.homeValue}
              bValue={row.awayValue}
              aPct={row.homePct}
              aInkClass={row.homePct > 50 ? "text-ink-primary" : "text-ink-secondary"}
              bInkClass={row.homePct < 50 ? "text-ink-primary" : "text-ink-secondary"}
              aBarClass={isZero ? "bg-border-subtle" : "bg-accent-live"}
              bBarClass={isZero ? "bg-border-subtle" : "bg-ink-secondary"}
            />
          );
        })}
      </section>

      <section className="flex shrink-0 flex-col gap-3 border-b border-border-subtle p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-heading-sm">Timeline</h3>
          <span className="text-label-sm text-ink-muted">{match.timeline.length} events</span>
        </div>
        <ol className="flex flex-col">
          {match.timeline.map((event, i) => (
            <TimelineItem
              key={`${event.minute}-${event.title}-${i}`}
              event={event}
              seriesColorClass={event.teamCode === match.homeTeam.code ? "bg-accent-live" : "bg-ink-secondary"}
              showConnector={i < match.timeline.length - 1}
            />
          ))}
        </ol>
      </section>

      <section className="flex grow flex-col gap-3 p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-heading-sm">Lineups</h3>
          <span className="text-label-sm text-ink-muted">▲ on · ▼ off</span>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {match.lineups.map((team) => (
            <div key={team.code} className="flex flex-col gap-2.5">
              <div className="flex h-9 items-center gap-2 border-b border-border-strong">
                <span
                  className={`size-2 rounded-[2px] ${team.code === match.homeTeam.code ? "bg-accent-live" : "bg-ink-secondary"}`}
                />
                <span className="grow text-heading-sm">{team.name}</span>
                <span className="font-mono text-data-sm text-ink-muted">{team.shape}</span>
              </div>
              {team.groups.map((group) => (
                <div key={group.name} className="flex flex-col">
                  <span className="flex h-[22px] items-center text-label-sm text-ink-muted">
                    {group.name}
                  </span>
                  {group.players.map((player) => (
                    <div key={player.name} className="flex h-7 items-center gap-2">
                      <span className="w-5 font-mono text-data-sm text-ink-muted">
                        {player.number}
                      </span>
                      <span className="min-w-0 grow truncate text-body-sm">{player.name}</span>
                      {player.mark ? (
                        <span
                          className={`font-mono text-data-sm ${player.mark.startsWith("▲") ? "text-data-positive" : "text-data-negative"}`}
                        >
                          {player.mark}
                        </span>
                      ) : null}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}
