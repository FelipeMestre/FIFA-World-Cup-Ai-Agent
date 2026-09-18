import type { TeamSummary } from "@/features/chat/types";

/**
 * Illustrative sample data (design/README.md: "illustrative placeholders,
 * not real results"), sourced from WidgetTeam.dc.html + PanelTeam.dc.html's
 * own `renderVals()` scripts. Team: Argentina.
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
};
