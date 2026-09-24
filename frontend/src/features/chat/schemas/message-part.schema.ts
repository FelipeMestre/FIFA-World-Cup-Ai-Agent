import { z } from "zod";

/**
 * Runtime validation for the backend's `MessagePart` discriminated union
 * (design/README.md's widget contract). `type: "team_widget"`,
 * `"match_widget"`, and `"player_widget"` are sent live by the backend's
 * `get_team_analysis`, `get_match_analysis`, and `get_player_analysis`
 * tools; `"compare_widget"` remains validated defensively so a payload that
 * doesn't yet match our rich widget shape degrades to a fallback instead of
 * crashing the thread.
 */

const positionSchema = z.enum(["GK", "DEF", "MID", "FWD"]);
const resultLetterSchema = z.enum(["W", "D", "L"]);

const teamSummarySchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  scopeLabel: z.string(),
  standingLabel: z.string(),
  record: z.object({
    won: z.number(),
    drawn: z.number(),
    lost: z.number(),
    goalsFor: z.number(),
    goalsAgainst: z.number(),
  }),
  goalDifference: z.number(),
  concededPerGame: z.number(),
  cleanSheets: z.number(),
  avgPossessionPct: z.number(),
  goalsByMatch: z.array(
    z.object({
      opponentCode: z.string(),
      goalsFor: z.number(),
      goalsAgainst: z.number(),
    }),
  ),
  tournamentAverages: z.array(
    z.object({ label: z.string(), value: z.string(), fieldValue: z.string(), delta: z.string() }),
  ),
  matchResults: z.array(
    z.object({
      stage: z.string(),
      opponentCode: z.string(),
      opponentName: z.string(),
      score: z.string(),
      result: resultLetterSchema,
    }),
  ),
  discipline: z.object({
    yellowCards: z.number(),
    redCards: z.number(),
    fouls: z.number(),
    yellowPerMatch: z.number(),
    fieldYellowPerMatch: z.number(),
  }),
  stageCaption: z.string(),
});

const matchEventSchema = z.object({
  minute: z.string(),
  kind: z.enum(["goal", "card", "var", "sub"]),
  teamCode: z.string(),
  title: z.string(),
  // Backend sends these keys as JSON `null`, never omits them -- `.optional()`
  // alone rejects `null` and would fail the whole widget's validation (same
  // gotcha as playerSummarySchema's `percentile` below).
  detail: z.string().nullable().optional(),
  subOn: z.string().nullable().optional(),
  subOff: z.string().nullable().optional(),
});

const matchSummarySchema = z.object({
  id: z.string(),
  stageLabel: z.string(),
  dateLabel: z.string(),
  venueLabel: z.string().nullable().optional(),
  homeTeam: z.object({ code: z.string(), name: z.string() }),
  awayTeam: z.object({ code: z.string(), name: z.string() }),
  homeScore: z.number(),
  awayScore: z.number(),
  statusLabel: z.string(),
  homeScorers: z.string(),
  awayScorers: z.string(),
  stats: z.array(
    z.object({ label: z.string(), homeValue: z.string(), awayValue: z.string(), homePct: z.number() }),
  ),
  events: z.array(matchEventSchema),
  playerOfMatch: z.object({
    name: z.string(),
    teamCode: z.string(),
    position: positionSchema,
    note: z.string(),
  }),
  timeline: z.array(matchEventSchema),
  lineups: z.array(
    z.object({
      code: z.string(),
      name: z.string(),
      shape: z.string(),
      groups: z.array(
        z.object({
          name: z.union([positionSchema, z.literal("Subs used")]),
          players: z.array(
            z.object({
              number: z.number(),
              name: z.string(),
              mark: z.string().nullable().optional(),
            }),
          ),
        }),
      ),
    }),
  ),
  footerCaption: z.string(),
});

const playerSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  initials: z.string(),
  teamCode: z.string(),
  position: positionSchema,
  appearances: z.number(),
  minutes: z.number(),
  scopeLabel: z.string(),
  tierLabel: z.string(),
  tierSegments: z.number(),
  disciplineLabel: z.string(),
  chips: z.array(z.object({ label: z.string(), value: z.string() })),
  footerCaption: z.string(),
  fullBreakdown: z.array(
    z.object({
      stat: z.string(),
      total: z.string(),
      perNinety: z.string(),
      // Backend sends this key as JSON `null`, never omits it -- `.optional()`
      // alone rejects `null` and would fail the whole widget's validation.
      percentile: z.number().nullable(),
    }),
  ),
  perNinetyVsPositionAverage: z.array(
    z.object({ label: z.string(), value: z.number(), positionAverage: z.number() }),
  ),
  clubProfile: z
    .object({
      preferredFoot: z.string().nullable(),
      subPosition: z.string().nullable(),
      heightCm: z.number().nullable(),
      dateOfBirth: z.string().nullable(),
      citizenship: z.string().nullable(),
      currentClub: z.string().nullable(),
      marketValueEur: z.number().nullable(),
      highestMarketValueEur: z.number().nullable(),
      internationalCaps: z.number().nullable(),
      internationalGoals: z.number().nullable(),
    })
    .nullable()
    .optional(),
  transfers: z
    .array(
      z.object({
        transferDate: z.string(),
        season: z.string().nullable(),
        fromClub: z.string(),
        toClub: z.string(),
        feeEur: z.number().nullable(),
        marketValueEur: z.number().nullable(),
      }),
    )
    .optional(),
  careerSeasons: z
    .array(
      z.object({
        season: z.string(),
        team: z.string().nullable(),
        competitionId: z.string(),
        competition: z.string(),
        appearances: z.number(),
        minutes: z.number(),
        goals: z.number(),
        assists: z.number(),
        yellowCards: z.number(),
        redCards: z.number(),
      }),
    )
    .optional(),
});

const comparisonPlayerRefSchema = z.object({
  id: z.string(),
  initials: z.string(),
  name: z.string(),
  teamCode: z.string(),
  position: positionSchema,
  minutes: z.number(),
});

const playerComparisonSchema = z.object({
  id: z.string(),
  normalization: z.enum(["per90", "totals"]),
  scopeLabel: z.string(),
  playerA: comparisonPlayerRefSchema,
  playerB: comparisonPlayerRefSchema,
  rows: z.array(
    z.object({
      label: z.string(),
      // Backend sends this key as JSON `null`, never omits it -- `.optional()`
      // alone rejects `null` and would fail the whole widget's validation.
      note: z.string().nullable().optional(),
      playerAPerNinety: z.string(),
      playerBPerNinety: z.string(),
      playerATotal: z.string(),
      playerBTotal: z.string(),
      playerAIsBetter: z.boolean(),
      playerBIsBetter: z.boolean(),
      playerATotalIsBetter: z.boolean(),
      playerBTotalIsBetter: z.boolean(),
      playerAPercentile: z.number().nullable().optional(),
      playerBPercentile: z.number().nullable().optional(),
    }),
  ),
  insights: z.array(z.string()),
  minMinutesCaption: z.string(),
});

export const messagePartSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("text"), content: z.string() }),
  z.object({ type: z.literal("team_widget"), data: teamSummarySchema }),
  z.object({ type: z.literal("match_widget"), data: matchSummarySchema }),
  z.object({ type: z.literal("player_widget"), data: playerSummarySchema }),
  z.object({ type: z.literal("compare_widget"), data: playerComparisonSchema }),
]);

/** Loosely typed part as received over the wire, before validation. */
export type RawMessagePart = { type: string; [key: string]: unknown };
