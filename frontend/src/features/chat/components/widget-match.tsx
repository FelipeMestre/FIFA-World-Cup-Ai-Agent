"use client";

import { Goal, RectangleHorizontal, Star } from "lucide-react";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { SplitBarRow } from "@/features/chat/components/comparison-row";
import { WidgetFrame } from "@/features/chat/components/widget-frame";
import type { MatchSummary } from "@/features/chat/types";

/** Match analysis widget (design/artboards/WidgetMatch.dc.html). */
export function WidgetMatch({
  match,
  active,
  onViewDetails,
}: {
  match: MatchSummary;
  active: boolean;
  onViewDetails: () => void;
}) {
  return (
    <WidgetFrame
      ariaLabel={`Match analysis: ${match.homeTeam.name} ${match.homeScore}, ${match.awayTeam.name} ${match.awayScore}`}
      icon={<RectangleHorizontal className="size-4" aria-hidden />}
      label="Match analysis"
      scopeText={match.dateLabel}
      footerCaption={match.footerCaption}
      active={active}
      onViewDetails={onViewDetails}
    >
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border-subtle px-4 pt-2">
        <span className="h-[22px] rounded-sm border border-border-strong px-2 text-label-sm text-ink-secondary">
          {match.stageLabel}
        </span>
      </div>

      <div className="grid shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 pt-5 pb-4">
        <div className="flex flex-col items-center gap-1.5">
          <AvatarBadge label={match.homeTeam.code} size={44} />
          <span className="text-heading-sm">{match.homeTeam.name}</span>
          <span className="h-[3px] w-5 rounded-sm bg-accent-live" />
        </div>
        <div className="flex flex-col items-center gap-1">
          <div className="flex items-center gap-3 font-mono text-data-xl">
            <span className="text-ink-secondary">{match.homeScore}</span>
            <span className="text-[24px] text-ink-muted">–</span>
            <span>{match.awayScore}</span>
          </div>
          <span className="text-label-sm text-ink-muted">{match.statusLabel}</span>
        </div>
        <div className="flex flex-col items-center gap-1.5">
          <AvatarBadge label={match.awayTeam.code} size={44} />
          <span className="text-heading-sm">{match.awayTeam.name}</span>
          <span className="h-[3px] w-5 rounded-sm bg-ink-secondary" />
        </div>
      </div>

      <div className="flex shrink-0 flex-col gap-3 px-4 pb-4">
        {/* The compact widget shows only its 3 headline rows; PanelMatch shows all of match.stats. */}
        {match.stats.slice(0, 3).map((row) => (
          <SplitBarRow
            key={row.label}
            label={row.label}
            aValue={row.homeValue}
            bValue={row.awayValue}
            aPct={row.homePct}
            aInkClass={row.homePct >= 50 ? "text-ink-primary" : "text-ink-secondary"}
            bInkClass={row.homePct < 50 ? "text-ink-primary" : "text-ink-secondary"}
          />
        ))}
      </div>

      <div className="flex grow flex-wrap items-start gap-4 border-t border-border-subtle p-4">
        <div className="flex min-w-[280px] flex-1 flex-col">
          {match.events.map((event) => (
            <div key={`${event.minute}-${event.title}`} className="flex h-7 items-center gap-2.5">
              <span className="w-7 text-right font-mono text-data-sm text-ink-muted">
                {event.minute}
              </span>
              <Goal className="size-4 text-ink-primary" aria-label="Goal" />
              <span className="min-w-0 grow truncate text-body-md">{event.title}</span>
              <span className="flex items-center gap-1 font-mono text-data-sm text-ink-muted">
                <span
                  className={`size-2 rounded-[2px] ${event.teamCode === match.homeTeam.code ? "bg-accent-live" : "bg-ink-secondary"}`}
                />
                {event.teamCode}
              </span>
            </div>
          ))}
        </div>
        <div className="flex min-w-[180px] flex-1 flex-col gap-1 rounded-sm border border-border-subtle bg-surface-900 px-3 py-2.5">
          <span className="flex items-center gap-1.5 text-label-sm text-ink-muted">
            <Star className="size-3.5" aria-hidden />
            Player of the match
          </span>
          <span className="text-heading-sm">{match.playerOfMatch.name}</span>
          <span className="text-body-sm text-ink-secondary">{match.playerOfMatch.note}</span>
        </div>
      </div>
    </WidgetFrame>
  );
}
