import type { ComparisonPlayer } from "@/features/chat/team-comparison";
import type { TeamSummary } from "@/features/chat/types";
import {
  argentinaDef,
  argentinaFwd,
  argentinaGk,
  argentinaMid,
} from "@/features/chat/sample-data/team-comparison-squad";
import { sampleTeamComparison } from "@/features/chat/sample-data/team-comparison";

/**
 * Illustrative sample data (design/README.md: "illustrative placeholders,
 * not real results"), sourced from WidgetTeam.dc.html + PanelTeam.dc.html's
 * own `renderVals()` scripts. Squad identity reuses the Argentina side of
 * the team-comparison sample.
 */

const TEAM_MATCH_ROWS: [string, number, number][] = [
  ["ALG", 3, 0],
  ["AUT", 2, 0],
  ["JOR", 1, 1],
  ["NGA", 3, 1],
  ["MEX", 2, 0],
  ["NED", 2, 1],
  ["BRA", 1, 2],
];

const argentina = sampleTeamComparison.teamA;

function rollup(players: ComparisonPlayer[]) {
  return {
    minutes: players.reduce((sum, row) => sum + row.minutes, 0),
    marketValueEur: players.reduce((sum, row) => sum + row.marketValueEur, 0),
    goals: players.reduce((sum, row) => sum + row.goals, 0),
    assists: players.reduce((sum, row) => sum + row.assists, 0),
  };
}

export const sampleTeam: TeamSummary = {
  id: "team-arg",
  code: "ARG",
  name: "Argentina",
  scopeLabel: "WC 2026 · 7 matches",
  standingLabel: "Semifinalist · out 1–2 to Brazil",
  record: { won: 5, drawn: 1, lost: 1, goalsFor: 14, goalsAgainst: 5 },
  goalDifference: 9,
  concededPerGame: 0.71,
  cleanSheets: 3,
  avgPossessionPct: 58.4,
  goalsByMatch: TEAM_MATCH_ROWS.map(([opponentCode, goalsFor, goalsAgainst]) => ({
    opponentCode,
    goalsFor,
    goalsAgainst,
  })),
  tournamentAverages: [
    { label: "Possession", value: "58.4%", fieldValue: "50.0%", delta: "▲ 8.4" },
    { label: "Shots", value: "15.3", fieldValue: "12.4", delta: "▲ 2.9" },
    { label: "Shots on target", value: "6.1", fieldValue: "4.3", delta: "▲ 1.8" },
    { label: "Corners", value: "6.4", fieldValue: "4.9", delta: "▲ 1.5" },
    { label: "Fouls", value: "10.9", fieldValue: "12.1", delta: "▼ 1.2" },
    { label: "Offsides", value: "1.7", fieldValue: "1.9", delta: "▼ 0.2" },
    { label: "Goals per game", value: "2.00", fieldValue: "1.20", delta: "▲ 0.80" },
    { label: "Goals conceded / game", value: "0.71", fieldValue: "1.20", delta: "▲ 0.49" },
    { label: "xG per game", value: "1.77", fieldValue: "1.20", delta: "▲ 0.57" },
    { label: "xG against / game", value: "0.73", fieldValue: "1.20", delta: "▲ 0.47" },
    { label: "xG difference / game", value: "+1.04", fieldValue: "+0.00", delta: "▲ 1.04" },
    { label: "Shot accuracy", value: "39.9%", fieldValue: "34.7%", delta: "▲ 5.20" },
    { label: "Conversion", value: "32.8%", fieldValue: "27.9%", delta: "▲ 4.90" },
    { label: "Clean sheets / game", value: "0.43", fieldValue: "0.25", delta: "▲ 0.18" },
    { label: "Group points", value: "7", fieldValue: "4", delta: "▲ 3.00" },
  ],
  matchResults: [
    { stage: "MD1", opponentCode: "ALG", opponentName: "Algeria", score: "3–0", result: "W" },
    { stage: "MD2", opponentCode: "AUT", opponentName: "Austria", score: "2–0", result: "W" },
    { stage: "MD3", opponentCode: "JOR", opponentName: "Jordan", score: "1–1", result: "D" },
    { stage: "R32", opponentCode: "NGA", opponentName: "Nigeria", score: "3–1", result: "W" },
    { stage: "R16", opponentCode: "MEX", opponentName: "Mexico", score: "2–0", result: "W" },
    { stage: "QF", opponentCode: "NED", opponentName: "Netherlands", score: "2–1", result: "W" },
    { stage: "SF", opponentCode: "BRA", opponentName: "Brazil", score: "1–2", result: "L" },
  ],
  discipline: {
    yellowCards: 11,
    redCards: 0,
    fouls: 76,
    yellowPerMatch: 1.57,
    fieldYellowPerMatch: 1.9,
  },
  stageCaption: "Group stage to semifinal",
  confederation: argentina.confederation,
  groupLetter: argentina.groupLetter,
  managerName: argentina.managerName,
  fifaRankingPreTournament: argentina.fifaRankingPreTournament,
  squad: argentina.squad,
  group: argentina.group,
  topScorer: argentina.topScorer,
  topAssister: argentina.topAssister,
  mostMinutes: argentina.mostMinutes,
  positions: [
    { position: "GK", players: [argentinaGk], rollup: rollup([argentinaGk]) },
    { position: "DEF", players: [argentinaDef], rollup: rollup([argentinaDef]) },
    { position: "MID", players: [argentinaMid], rollup: rollup([argentinaMid]) },
    { position: "FWD", players: [argentinaFwd], rollup: rollup([argentinaFwd]) },
  ],
};
