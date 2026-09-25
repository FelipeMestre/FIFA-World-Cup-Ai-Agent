import type { ComparisonPlayer, PositionGroup } from "@/features/chat/team-comparison";
import type { Position } from "@/features/chat/types";

function player(partial: {
  id: string;
  name: string;
  initials: string;
  position: Position;
  club: string;
  age: number;
  minutes: number;
  goals?: number;
  assists?: number;
  value?: number;
  cleanSheets?: number | null;
  saves?: number | null;
  goalsConceded?: number | null;
}): ComparisonPlayer {
  const goals = partial.goals ?? 0;
  const assists = partial.assists ?? 0;
  const per90 = partial.minutes > 0 ? Math.round(((goals + assists) * 90 * 100) / partial.minutes) / 100 : 0;
  const isGk = partial.position === "GK";
  return {
    id: partial.id,
    name: partial.name,
    initials: partial.initials,
    position: partial.position,
    club: partial.club,
    age: partial.age,
    heightCm: isGk ? 195 : 180,
    marketValueEur: partial.value ?? 20_000_000,
    caps: 40,
    appearances: 7,
    starts: partial.minutes > 0 ? 6 : 0,
    minutes: partial.minutes,
    goals,
    assists,
    goalsPer90: partial.minutes > 0 ? Math.round((goals * 90 * 100) / partial.minutes) / 100 : 0,
    assistsPer90: partial.minutes > 0 ? Math.round((assists * 90 * 100) / partial.minutes) / 100 : 0,
    goalContributionsPer90: per90,
    yellowCards: 1,
    redCards: 0,
    penaltyGoals: 0,
    ownGoals: 0,
    cleanSheets: isGk ? (partial.cleanSheets ?? 0) : null,
    saves: isGk ? (partial.saves ?? 0) : null,
    goalsConceded: isGk ? (partial.goalsConceded ?? 0) : null,
    savesPer90: isGk && partial.minutes > 0 ? Math.round(((partial.saves ?? 0) * 90 * 100) / partial.minutes) / 100 : null,
    goalsConcededPer90:
      isGk && partial.minutes > 0
        ? Math.round(((partial.goalsConceded ?? 0) * 90 * 100) / partial.minutes) / 100
        : null,
  };
}

export function samplePositionGroup(position: Position, teamA: ComparisonPlayer[], teamB: ComparisonPlayer[]): PositionGroup {
  const rollup = (players: ComparisonPlayer[]) => ({
    minutes: players.reduce((sum, row) => sum + row.minutes, 0),
    marketValueEur: players.reduce((sum, row) => sum + row.marketValueEur, 0),
    goals: players.reduce((sum, row) => sum + row.goals, 0),
    assists: players.reduce((sum, row) => sum + row.assists, 0),
  });
  return {
    position,
    teamAPlayers: teamA,
    teamBPlayers: teamB,
    teamARollup: rollup(teamA),
    teamBRollup: rollup(teamB),
  };
}

export const argentinaGk = player({
  id: "p-arg-gk",
  name: "Emiliano Martínez",
  initials: "EM",
  position: "GK",
  club: "Aston Villa",
  age: 33,
  minutes: 630,
  value: 28_000_000,
  cleanSheets: 3,
  saves: 18,
  goalsConceded: 5,
});
export const brazilGk = player({
  id: "p-bra-gk",
  name: "Alisson",
  initials: "AL",
  position: "GK",
  club: "Liverpool",
  age: 33,
  minutes: 570,
  value: 32_000_000,
  cleanSheets: 2,
  saves: 14,
  goalsConceded: 7,
});
export const argentinaDef = player({
  id: "p-arg-def",
  name: "Cristian Romero",
  initials: "CR",
  position: "DEF",
  club: "Tottenham",
  age: 28,
  minutes: 540,
  goals: 1,
  value: 55_000_000,
});
export const brazilDef = player({
  id: "p-bra-def",
  name: "Marquinhos",
  initials: "MA",
  position: "DEF",
  club: "Paris Saint-Germain",
  age: 32,
  minutes: 570,
  value: 40_000_000,
});
export const argentinaMid = player({
  id: "p-arg-mid",
  name: "Enzo Fernández",
  initials: "EF",
  position: "MID",
  club: "Chelsea",
  age: 25,
  minutes: 580,
  goals: 1,
  assists: 3,
  value: 75_000_000,
});
export const brazilMid = player({
  id: "p-bra-mid",
  name: "Bruno Guimarães",
  initials: "BG",
  position: "MID",
  club: "Newcastle",
  age: 28,
  minutes: 500,
  goals: 1,
  assists: 2,
  value: 70_000_000,
});
export const argentinaFwd = player({
  id: "p-arg-fwd",
  name: "Lautaro Martínez",
  initials: "LM",
  position: "FWD",
  club: "Inter",
  age: 28,
  minutes: 490,
  goals: 5,
  assists: 1,
  value: 110_000_000,
});
export const brazilFwd = player({
  id: "p-bra-fwd",
  name: "Vinícius Júnior",
  initials: "VJ",
  position: "FWD",
  club: "Real Madrid",
  age: 26,
  minutes: 520,
  goals: 4,
  assists: 2,
  value: 150_000_000,
});

