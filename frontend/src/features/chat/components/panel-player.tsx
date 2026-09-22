"use client";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { BenchmarkBarRow } from "@/features/chat/components/comparison-row";
import { PanelHeader } from "@/features/chat/components/panel-header";
import {
  DisciplineTag,
  PositionTag,
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
  const maxPerNinety = Math.max(
    1,
    ...player.perNinetyVsPositionAverage.map(
      (r) => Math.max(r.value, r.positionAverage) * 1.15,
    ),
  );

  return (
    <aside
      aria-label={`Player detail: ${player.name}`}
      className="flex h-full flex-col bg-surface-900"
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
            <span className="text-body-sm text-ink-secondary">
              {player.teamCode} ·{" "}
              {player.position === "GK" ? "Goalkeeper" : player.position} ·{" "}
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
                className="px-2 text-right text-label-sm text-ink-muted"
              >
                Per 90
              </th>
              <th
                scope="col"
                className="px-2 pr-3.5 text-right text-label-sm text-ink-muted"
              >
                Pct · {player.position}
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
                <td className="px-2 text-right font-mono text-data-md text-ink-secondary">
                  {row.perNinety}
                </td>
                <td className="px-2 pr-3.5">
                  {row.percentile != null ? (
                    <div className="flex items-center justify-end gap-2">
                      <div className="h-1 w-14 rounded-sm bg-border-subtle">
                        <div
                          className="h-1 rounded-sm bg-accent-live"
                          style={{ width: `${row.percentile}%` }}
                        />
                      </div>
                      <span className="w-6 text-right font-mono text-data-sm">
                        {row.percentile}
                      </span>
                    </div>
                  ) : (
                    <div className="text-right font-mono text-data-sm text-ink-muted">
                      —
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="flex grow flex-col gap-3.5 p-5">
        <h3 className="text-heading-sm">Per 90 vs {player.position} average</h3>
        <div className="flex gap-4 text-data-sm text-ink-secondary">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm bg-accent-live" />
            {player.name.split(" ").at(-1)}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-0.5 bg-data-neutral" />
            {player.position} average
          </span>
        </div>
        {player.perNinetyVsPositionAverage.map((row) => (
          <BenchmarkBarRow
            key={row.label}
            label={row.label}
            value={row.value.toFixed(2)}
            average={row.positionAverage.toFixed(2)}
            valuePct={Math.round((row.value / maxPerNinety) * 100)}
            averagePct={Math.round((row.positionAverage / maxPerNinety) * 100)}
          />
        ))}
        <p className="text-body-sm text-ink-muted">
          Per 90 = total ÷ minutes × 90. {player.position} average and
          percentiles use players at this position with at least 270 minutes.
        </p>
      </section>
    </aside>
  );
}
