"use client";

import { ArrowLeftRight, ChevronDown } from "lucide-react";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { PanelHeader } from "@/features/chat/components/panel-header";
import type { PlayerComparison } from "@/features/chat/types";

/** Player comparison side panel (design/artboards/PanelCompare.dc.html). */
export function PanelCompare({
  comparison,
  fromMessage,
  onClose,
  onJumpToMessage,
  isSheet = false,
}: {
  comparison: PlayerComparison;
  fromMessage: string;
  onClose: () => void;
  onJumpToMessage: () => void;
  isSheet?: boolean;
}) {
  const { playerA, playerB } = comparison;

  return (
    <aside
      aria-label={`Player comparison: ${playerA.name} and ${playerB.name}`}
      className="flex h-full flex-col bg-surface-900"
    >
      <PanelHeader
        entityLabel="Player comparison"
        title={`${playerA.name.split(" ").at(-1)} vs ${playerB.name.split(" ").at(-1)}`}
        fromMessage={fromMessage}
        onClose={onClose}
        onJumpToMessage={onJumpToMessage}
        isSheet={isSheet}
      />

      <section className="flex shrink-0 flex-col gap-3 border-b border-border-subtle p-5">
        <div className="grid grid-cols-2 gap-3">
          {[
            {
              player: playerA,
              slot: "Player A",
              color: "var(--color-accent-live)",
            },
            {
              player: playerB,
              slot: "Player B",
              color: "var(--color-ink-secondary)",
            },
          ].map(({ player, slot, color }) => (
            <div
              key={player.id}
              className="flex flex-col gap-2.5 rounded-lg border border-border-strong bg-surface-800 p-3.5"
            >
              <span className="flex items-center gap-1.5 text-label-sm text-ink-muted">
                <span
                  className="size-2 rounded-[2px]"
                  style={{ background: color }}
                />
                {slot}
              </span>
              <div className="flex items-center gap-2.5">
                <AvatarBadge
                  label={player.initials}
                  size={40}
                  seriesColor={color}
                />
                <div className="flex min-w-0 flex-col">
                  <span className="truncate text-heading-sm">
                    {player.name}
                  </span>
                  <span className="text-body-sm text-ink-secondary">
                    {player.teamCode} · {player.position} · {player.minutes} min
                  </span>
                </div>
              </div>
              <button
                type="button"
                aria-label={`Swap ${slot.toLowerCase()}`}
                className="focus-ring flex h-11 items-center gap-2 rounded-md border border-border-strong bg-surface-700 px-3 text-label-md text-ink-primary"
              >
                <ArrowLeftRight className="size-4" aria-hidden />
                <span className="grow text-left">Swap player</span>
                <ChevronDown className="size-4 text-ink-muted" aria-hidden />
              </button>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between gap-3">
          <div
            role="group"
            aria-label="Normalization"
            className="flex gap-0.5 rounded-md border border-border-strong bg-surface-950 p-0.5"
          >
            <button
              type="button"
              aria-pressed="true"
              className="h-9 rounded-sm bg-surface-600 px-3.5 text-label-md text-ink-primary"
            >
              Per 90
            </button>
            <button
              type="button"
              aria-pressed="false"
              className="h-9 rounded-sm px-3.5 text-label-md text-ink-secondary"
            >
              Totals
            </button>
          </div>
          <span className="text-body-sm text-ink-muted">
            {comparison.scopeLabel}
          </span>
        </div>
      </section>

      <section className="flex grow flex-col gap-3 p-5">
        <table className="w-full border-collapse overflow-hidden rounded-lg border border-border-strong bg-surface-800">
          <thead>
            <tr className="h-9 border-b border-border-strong">
              <th
                scope="col"
                className="px-3.5 text-left text-label-sm text-ink-muted"
              >
                Per 90
              </th>
              <th
                scope="col"
                className="px-3 text-left text-label-sm text-ink-muted"
              >
                <span className="mr-1.5 inline-block size-2 rounded-[2px] bg-accent-live" />
                {playerA.name.split(" ").at(-1)}
              </th>
              <th
                scope="col"
                className="px-3 pr-3.5 text-left text-label-sm text-ink-muted"
              >
                <span className="mr-1.5 inline-block size-2 rounded-[2px] bg-ink-secondary" />
                {playerB.name.split(" ").at(-1)}
              </th>
            </tr>
          </thead>
          <tbody>
            {comparison.rows.map((row) => (
              <tr
                key={row.label}
                className="h-14 border-b border-border-subtle"
              >
                <th scope="row" className="px-3.5 text-left font-normal">
                  <span className="block text-body-md text-ink-primary">
                    {row.label}
                  </span>
                  {row.note ? (
                    <span className="block text-data-sm text-ink-muted">
                      {row.note}
                    </span>
                  ) : null}
                </th>
                <td className="px-3">
                  <ComparisonCell
                    value={row.playerAValue}
                    isBetter={row.playerAIsBetter}
                    percentile={row.playerAPercentile}
                    barClass="bg-accent-live"
                  />
                </td>
                <td className="px-3 pr-3.5">
                  <ComparisonCell
                    value={row.playerBValue}
                    isBetter={row.playerBIsBetter}
                    percentile={row.playerBPercentile}
                    barClass="bg-ink-secondary"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-body-sm text-ink-muted">
          ▲ marks the better figure in each row. Percentile rank within
          position, players with at least 270 minutes. Minutes shown as totals.
        </p>
      </section>
    </aside>
  );
}

function ComparisonCell({
  value,
  isBetter,
  percentile,
  barClass,
}: {
  value: string;
  isBetter: boolean;
  percentile?: number;
  barClass: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span
        className={`font-mono text-data-md ${isBetter ? "text-ink-primary" : "text-ink-secondary"}`}
      >
        {value}{" "}
        {isBetter ? (
          <span className="text-data-sm text-accent-live">▲</span>
        ) : null}
      </span>
      {percentile != null ? (
        <span className="flex items-center gap-1.5">
          <span className="flex h-1 w-14 rounded-sm bg-border-subtle">
            <span
              className={`h-1 rounded-sm ${barClass}`}
              style={{ width: `${percentile}%` }}
            />
          </span>
          <span className="font-mono text-data-sm text-ink-muted">
            {ordinal(percentile)}
          </span>
        </span>
      ) : null}
    </div>
  );
}

function ordinal(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n}st`;
  if (mod10 === 2 && mod100 !== 12) return `${n}nd`;
  if (mod10 === 3 && mod100 !== 13) return `${n}rd`;
  return `${n}th`;
}
