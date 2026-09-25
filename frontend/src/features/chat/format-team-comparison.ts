import type { ComparedStat, ComparisonPlayer } from "@/features/chat/team-comparison";
import type { Position } from "@/features/chat/types";

export function formatRecord(record: { won: number; drawn: number; lost: number }): string {
  return `${record.won}–${record.drawn}–${record.lost}`;
}

export function formatMarketValue(value: number | null): string {
  if (value == null) return "—";
  const abs = Math.abs(value);
  const sign = value < 0 ? "−" : "";
  if (abs >= 1_000_000_000) return `${sign}€${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}€${Math.round(abs / 1_000_000)}M`;
  return `${sign}€${abs.toLocaleString("en-US")}`;
}

export function formatAge(age: number | null): string {
  return age == null ? "—" : age.toFixed(1);
}

export function formatCount(value: number | null): string {
  return value == null ? "—" : String(value);
}

/** Side A's share of a non-negative split. Signed stats stay centered. */
export function barShare(stat: ComparedStat): number {
  if (stat.teamAValue < 0 || stat.teamBValue < 0) return 50;
  const total = stat.teamAValue + stat.teamBValue;
  if (total === 0) return 50;
  return Math.round((stat.teamAValue / total) * 100);
}

export function playerLine(player: ComparisonPlayer, position: Position): string {
  if (position === "GK") {
    return `${player.minutes} min · ${formatCount(player.cleanSheets)} clean sheets · ${formatCount(player.saves)} saves · ${formatCount(player.goalsConceded)} conceded`;
  }
  return `${player.minutes} min · ${player.goals} goals · ${player.assists} assists · ${player.goalContributionsPer90.toFixed(2)} /90`;
}
