"use client";

import { positionLabel } from "@/features/chat/components/profile-tag";
import { formatMarketValue, playerLine } from "@/features/chat/format-team-comparison";
import type {
  ComparisonPlayer,
  PositionGroup,
  PositionRollup,
} from "@/features/chat/team-comparison";

function PlayerColumn({
  code,
  players,
  rollup,
  align,
}: {
  code: string;
  players: ComparisonPlayer[];
  rollup: PositionRollup;
  align: "start" | "end";
}) {
  const end = align === "end";
  return (
    <div className={`flex flex-col gap-ds-2 ${end ? "items-end text-right" : "items-start"}`}>
      <span className={end ? "font-mono text-data-sm text-ink-secondary" : "font-mono text-data-sm text-accent-live"}>
        {code}
      </span>
      {players.length === 0 ? (
        <span className="text-body-sm text-ink-muted">No squad players</span>
      ) : (
        players.map((player) => (
          <div key={player.id} className="flex w-full flex-col gap-0.5 border-b border-border-subtle pb-ds-2">
            <span className="text-body-md">{player.name}</span>
            <span className="text-body-sm text-ink-secondary">
              {player.club} · {player.age} · {player.heightCm} cm
            </span>
            <span className="font-mono text-data-sm">{playerLine(player, player.position)}</span>
            <span className="font-mono text-data-sm text-ink-muted">
              {formatMarketValue(player.marketValueEur)} · {player.caps} caps
            </span>
          </div>
        ))
      )}
      <span className="font-mono text-data-sm text-ink-muted">
        {rollup.minutes} min · {formatMarketValue(rollup.marketValueEur)} · {rollup.goals} G · {rollup.assists} A
      </span>
    </div>
  );
}

/** GK vs GK, DEF vs DEF, and the same for midfield and attack. */
export function TeamComparePositions({
  teamACode,
  teamBCode,
  positions,
}: {
  teamACode: string;
  teamBCode: string;
  positions: PositionGroup[];
}) {
  return (
    <section className="flex flex-col gap-ds-5 p-ds-5">
      <h3 className="text-heading-sm">Squad by position</h3>
      {positions.map((group) => (
        <div key={group.position} className="flex flex-col gap-ds-3">
          <h4 className="text-label-sm text-ink-muted">{positionLabel(group.position)}</h4>
          <div className="grid grid-cols-2 gap-ds-4">
            <PlayerColumn
              code={teamACode}
              players={group.teamAPlayers}
              rollup={group.teamARollup}
              align="start"
            />
            <PlayerColumn
              code={teamBCode}
              players={group.teamBPlayers}
              rollup={group.teamBRollup}
              align="end"
            />
          </div>
        </div>
      ))}
    </section>
  );
}
