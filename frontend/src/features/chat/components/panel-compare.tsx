"use client";

import { useState } from "react";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { PanelHeader } from "@/features/chat/components/panel-header";
import { positionLabel } from "@/features/chat/components/profile-tag";
import type { PlayerComparison } from "@/features/chat/types";

type Normalization = "per90" | "totals";

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
  const [normalization, setNormalization] = useState<Normalization>(
    comparison.normalization,
  );

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
                    {player.teamCode} · {positionLabel(player.position)} · {player.minutes} min
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-body-sm text-ink-muted">
            {comparison.scopeLabel}
          </span>
          <div
            className="flex rounded-md border border-border-strong bg-surface-800 p-0.5"
            role="group"
            aria-label="Value normalization"
          >
            {[
              { key: "per90" as const, label: "Per 90" },
              { key: "totals" as const, label: "Totals" },
            ].map(({ key, label }) => (
              <button
                key={key}
                type="button"
                aria-pressed={normalization === key}
                onClick={() => setNormalization(key)}
                className={`rounded-[4px] px-2.5 py-1 text-label-sm transition-colors ${
                  normalization === key
                    ? "bg-surface-700 text-ink-primary"
                    : "text-ink-muted hover:text-ink-secondary"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
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
                {normalization === "per90" ? "Per 90" : "Totals"}
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
            {comparison.rows.map((row) => {
              const isPerNinety = normalization === "per90";
              const valueA = isPerNinety
                ? row.playerAPerNinety
                : row.playerATotal;
              const valueB = isPerNinety
                ? row.playerBPerNinety
                : row.playerBTotal;
              const aIsBetter = isPerNinety
                ? row.playerAIsBetter
                : row.playerATotalIsBetter;
              const bIsBetter = isPerNinety
                ? row.playerBIsBetter
                : row.playerBTotalIsBetter;
              return (
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
                      value={valueA}
                      isBetter={aIsBetter}
                      percentile={
                        isPerNinety ? row.playerAPercentile : undefined
                      }
                      barClass="bg-accent-live"
                    />
                  </td>
                  <td className="px-3 pr-3.5">
                    <ComparisonCell
                      value={valueB}
                      isBetter={bIsBetter}
                      percentile={
                        isPerNinety ? row.playerBPercentile : undefined
                      }
                      barClass="bg-ink-secondary"
                    />
                  </td>
                </tr>
              );
            })}
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
