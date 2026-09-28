"use client";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { PanelHeader } from "@/features/chat/components/panel-header";
import { PlayerSeasonTable } from "@/features/chat/components/player-season-table";
import { PlayerClubProfileFacts } from "@/features/chat/components/player-club-profile";
import { PlayerTransferPath } from "@/features/chat/components/player-transfer-path";
import {
  DisciplineTag,
  PositionTag,
  positionLabel,
  TeamCodeLabel,
  TierTag,
} from "@/features/chat/components/profile-tag";
import type { PlayerSummary } from "@/features/chat/types";

/** Player detail side panel (design/artboards/PanelPlayer.dc.html). */
export function PanelPlayer({
  player,
  fromMessage,
  onClose,
  onJumpToMessage,
  isSheet = false,
}: {
  player: PlayerSummary;
  fromMessage: string;
  onClose: () => void;
  onJumpToMessage: () => void;
  isSheet?: boolean;
}) {
  return (
    <aside
      aria-label={`Player detail: ${player.name}`}
      className="flex min-h-full flex-col bg-surface-900"
    >
      <PanelHeader
        entityLabel="Player detail"
        title={player.name}
        fromMessage={fromMessage}
        onClose={onClose}
        onJumpToMessage={onJumpToMessage}
        isSheet={isSheet}
      />

      <section className="flex shrink-0 flex-col gap-3.5 border-b border-border-subtle p-5">
        <div className="flex items-center gap-3.5">
          <AvatarBadge
            label={player.initials}
            size={64}
            className="text-heading-lg"
          />
          <div className="flex flex-col gap-0.5">
            <span className="text-heading-lg">{player.name}</span>
            <span className="flex flex-wrap items-center gap-1.5 text-body-sm text-ink-secondary">
              <TeamCodeLabel teamCode={player.teamCode} /> ·{" "}
              {positionLabel(player.position)} ·{" "}
              {player.scopeLabel}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <PositionTag position={player.position} />
          <TierTag label={player.tierLabel} filled={player.tierSegments} />
          <DisciplineTag label={player.disciplineLabel} />
        </div>
      </section>

      {player.clubProfile ? (
        <PlayerClubProfileFacts profile={player.clubProfile} layout="panel" />
      ) : null}

      <section className="flex shrink-0 flex-col gap-3 border-b border-border-subtle p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-heading-sm">Full breakdown</h3>
          <span className="text-label-sm text-ink-muted">Totals · per 90</span>
        </div>
        <table className="w-full border-collapse overflow-hidden rounded-lg border border-border-strong bg-surface-800">
          <thead>
            <tr className="h-9 border-b border-border-strong">
              <th
                scope="col"
                className="px-3.5 text-left text-label-sm text-ink-muted"
              >
                Stat
              </th>
              <th
                scope="col"
                className="px-2 text-right text-label-sm text-ink-muted"
              >
                Total
              </th>
              <th
                scope="col"
                className="px-2 pr-3.5 text-right text-label-sm text-ink-muted"
              >
                Per 90
              </th>
            </tr>
          </thead>
          <tbody>
            {player.fullBreakdown.map((row) => (
              <tr key={row.stat} className="h-10 border-b border-border-subtle">
                <th
                  scope="row"
                  className="px-3.5 text-left text-body-md font-normal text-ink-primary"
                >
                  {row.stat}
                </th>
                <td className="px-2 text-right font-mono text-data-md">
                  {row.total}
                </td>
                <td className="px-2 pr-3.5 text-right font-mono text-data-md text-ink-secondary">
                  {row.perNinety}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <PlayerTransferPath transfers={player.transfers ?? []} />
      <PlayerSeasonTable seasons={player.careerSeasons ?? []} />
    </aside>
  );
}
