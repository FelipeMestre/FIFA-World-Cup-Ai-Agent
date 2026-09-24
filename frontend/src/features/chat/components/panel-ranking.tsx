"use client";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { PanelHeader } from "@/features/chat/components/panel-header";
import { PositionTag, positionLabel } from "@/features/chat/components/profile-tag";
import { StatChip } from "@/features/chat/components/stat-chip";
import type { PlayerRanking, PlayerRankingRow } from "@/features/chat/types";

function optionalChip(
  label: string,
  value: number | null | undefined,
  hideZero = false,
): { label: string; value: string }[] {
  if (value == null || (hideZero && value === 0)) {
    return [];
  }
  return [{ label, value: String(value) }];
}

function uniqueChips(chips: { label: string; value: string }[]) {
  const seen = new Set<string>();
  return chips.filter((chip) => {
    if (seen.has(chip.label)) {
      return false;
    }
    seen.add(chip.label);
    return true;
  });
}

function playerInfoChips(row: PlayerRankingRow, rankByLabel: string) {
  return uniqueChips([
    { label: rankByLabel, value: row.value },
    { label: "Age", value: String(row.age) },
    { label: "Height", value: `${row.heightCm} cm` },
    { label: "Apps", value: String(row.appearances) },
    { label: "Minutes", value: String(row.minutes) },
    { label: "Goals", value: String(row.goals) },
    { label: "Assists", value: String(row.assists) },
    ...optionalChip("Starts", row.starts),
    ...optionalChip("Penalties", row.penaltyGoals, true),
    { label: "Yellows", value: String(row.yellowCards) },
    { label: "Reds", value: String(row.redCards) },
    ...optionalChip("Saves", row.saves),
    ...optionalChip("Clean sheets", row.cleanSheets),
    ...optionalChip("Goals conceded", row.goalsConceded),
  ]);
}

/** Side panel with roster and supporting stats for every ranked player. */
export function PanelRanking({
  ranking,
  fromMessage,
  onClose,
  onJumpToMessage,
  isSheet = false,
}: {
  ranking: PlayerRanking;
  fromMessage: string;
  onClose: () => void;
  onJumpToMessage: () => void;
  isSheet?: boolean;
}) {
  return (
    <aside
      aria-label={`Player ranking: ${ranking.rankByLabel}`}
      className="flex min-h-full flex-col bg-surface-900"
    >
      <PanelHeader
        entityLabel="Player ranking"
        title={ranking.rankByLabel}
        fromMessage={fromMessage}
        onClose={onClose}
        onJumpToMessage={onJumpToMessage}
        isSheet={isSheet}
      />
      <section className="flex shrink-0 flex-col gap-ds-1 border-b border-border-subtle p-ds-5">
        <span className="text-body-sm text-ink-secondary">{ranking.scopeLabel}</span>
        <span className="text-label-sm text-ink-muted">{ranking.footerCaption}</span>
      </section>
      <ol className="flex flex-col">
        {ranking.rows.map((row) => (
          <li
            key={row.playerId}
            className="flex flex-col gap-ds-3 border-b border-border-subtle p-ds-5"
          >
            <div className="flex items-start gap-ds-3">
              <span className="w-6 shrink-0 pt-1 font-mono text-data-sm text-ink-muted">
                {row.rank}
              </span>
              <AvatarBadge label={row.initials} size={40} className="text-label-sm" />
              <div className="flex min-w-0 grow flex-col gap-ds-2">
                <div className="flex items-baseline justify-between gap-ds-2">
                  <span className="truncate text-heading-sm text-ink-primary">{row.name}</span>
                  <span className="shrink-0 font-mono text-data-lg text-ink-primary">
                    {row.value}
                  </span>
                </div>
                <span className="text-label-sm text-ink-muted">
                  {row.teamCode} · {positionLabel(row.position)} · {row.clubTeam}
                </span>
                <div className="flex">
                  <PositionTag position={row.position} />
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-ds-2 sm:grid-cols-3">
              {playerInfoChips(row, ranking.rankByLabel).map((chip) => (
                <StatChip
                  key={`${row.playerId}-${chip.label}`}
                  label={chip.label}
                  value={chip.value}
                  variant="tile"
                />
              ))}
            </div>
          </li>
        ))}
      </ol>
    </aside>
  );
}
