import { z } from "zod";

const positionSchema = z.enum(["GK", "DEF", "MID", "FWD"]);
const resultLetterSchema = z.enum(["W", "D", "L"]);

const recordSchema = z.object({
  won: z.number(),
  drawn: z.number(),
  lost: z.number(),
  goalsFor: z.number(),
  goalsAgainst: z.number(),
});

const matchResultSchema = z.object({
  stage: z.string(),
  opponentCode: z.string(),
  opponentName: z.string(),
  score: z.string(),
  result: resultLetterSchema,
});

const ratesSchema = z.object({
  goalsPerGame: z.number(),
  concededPerGame: z.number(),
  xgFor: z.number(),
  xgAgainst: z.number(),
  xgDifference: z.number(),
  xgPerGame: z.number(),
  xgAgainstPerGame: z.number(),
  possessionPct: z.number(),
  shotsPerGame: z.number(),
  shotsOnTargetPerGame: z.number(),
  shotAccuracyPct: z.number(),
  conversionPct: z.number(),
  cornersPerGame: z.number(),
  foulsPerGame: z.number(),
  offsidesPerGame: z.number(),
  saves: z.number(),
  savesPerGame: z.number(),
  cleanSheets: z.number(),
  cleanSheetsPerGame: z.number(),
});

const squadSchema = z.object({
  rosterSize: z.number(),
  averageAge: z.number().nullable(),
  totalMarketValueEur: z.number(),
  youngestAge: z.number().nullable(),
  oldestAge: z.number().nullable(),
  under23Pct: z.number(),
  over30Pct: z.number(),
  topThreeValueSharePct: z.number(),
  distinctStarters: z.number(),
  starterMinutesSharePct: z.number(),
  transfermarktAverageAge: z.number().nullable(),
  transfermarktMarketValueEur: z.number().nullable(),
  transfermarktSquadSize: z.number().nullable(),
});

const leaderSchema = z.object({
  playerId: z.string(),
  name: z.string(),
  position: positionSchema,
  goals: z.number(),
  assists: z.number(),
  minutes: z.number(),
});

const comparedTeamSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  confederation: z.string(),
  groupLetter: z.string().nullable(),
  managerName: z.string().nullable(),
  fifaRankingPreTournament: z.number().nullable(),
  eloRating: z.number().nullable(),
  standingLabel: z.string(),
  stageCaption: z.string(),
  record: recordSchema,
  goalDifference: z.number(),
  rates: ratesSchema,
  discipline: z.object({
    yellowCards: z.number(),
    redCards: z.number(),
    fouls: z.number(),
    yellowPerMatch: z.number(),
  }),
  squad: squadSchema,
  group: z.object({
    played: z.number(),
    points: z.number(),
    goalDifference: z.number(),
  }),
  matchResults: z.array(matchResultSchema),
  topScorer: leaderSchema.nullable(),
  topAssister: leaderSchema.nullable(),
  mostMinutes: leaderSchema.nullable(),
});

const comparisonPlayerSchema = z.object({
  id: z.string(),
  name: z.string(),
  initials: z.string(),
  position: positionSchema,
  club: z.string(),
  age: z.number(),
  heightCm: z.number(),
  marketValueEur: z.number(),
  caps: z.number(),
  appearances: z.number(),
  starts: z.number(),
  minutes: z.number(),
  goals: z.number(),
  assists: z.number(),
  goalsPer90: z.number(),
  assistsPer90: z.number(),
  goalContributionsPer90: z.number(),
  yellowCards: z.number(),
  redCards: z.number(),
  penaltyGoals: z.number(),
  ownGoals: z.number(),
  cleanSheets: z.number().nullable(),
  saves: z.number().nullable(),
  goalsConceded: z.number().nullable(),
  savesPer90: z.number().nullable(),
  goalsConcededPer90: z.number().nullable(),
});

const rollupSchema = z.object({
  minutes: z.number(),
  marketValueEur: z.number(),
  goals: z.number(),
  assists: z.number(),
});

export const teamComparisonSchema = z.object({
  id: z.string(),
  scopeLabel: z.string(),
  teamA: comparedTeamSchema,
  teamB: comparedTeamSchema,
  comparedStats: z.array(
    z.object({
      label: z.string(),
      teamADisplay: z.string(),
      teamBDisplay: z.string(),
      fieldDisplay: z.string(),
      teamAValue: z.number(),
      teamBValue: z.number(),
      fieldValue: z.number(),
      higherIsBetter: z.boolean(),
      teamAIsBetter: z.boolean(),
      teamBIsBetter: z.boolean(),
    }),
  ),
  strengthsAndFlaws: z.array(
    z.object({
      side: z.enum(["a", "b"]),
      kind: z.enum(["strength", "flaw"]),
      label: z.string(),
      detail: z.string(),
    }),
  ),
  meetings: z.array(
    z.object({
      matchId: z.string(),
      stage: z.string(),
      teamAScore: z.number(),
      teamBScore: z.number(),
      teamAResult: resultLetterSchema,
      penaltyScore: z.string().nullable(),
    }),
  ),
  positions: z.array(
    z.object({
      position: positionSchema,
      teamAPlayers: z.array(comparisonPlayerSchema),
      teamBPlayers: z.array(comparisonPlayerSchema),
      teamARollup: rollupSchema,
      teamBRollup: rollupSchema,
    }),
  ),
});
