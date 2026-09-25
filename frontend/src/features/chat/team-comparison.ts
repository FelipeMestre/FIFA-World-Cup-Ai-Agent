import type { Position, ResultLetter, TeamMatchResult } from "@/features/chat/types";

export interface TeamRates {
  goalsPerGame: number;
  concededPerGame: number;
  xgFor: number;
  xgAgainst: number;
  xgDifference: number;
  xgPerGame: number;
  xgAgainstPerGame: number;
  possessionPct: number;
  shotsPerGame: number;
  shotsOnTargetPerGame: number;
  shotAccuracyPct: number;
  conversionPct: number;
  cornersPerGame: number;
  foulsPerGame: number;
  offsidesPerGame: number;
  saves: number;
  savesPerGame: number;
  cleanSheets: number;
  cleanSheetsPerGame: number;
}

export interface TeamDisciplineSummary {
  yellowCards: number;
  redCards: number;
  fouls: number;
  yellowPerMatch: number;
}

export interface SquadProfile {
  rosterSize: number;
  averageAge: number | null;
  totalMarketValueEur: number;
  youngestAge: number | null;
  oldestAge: number | null;
  under23Pct: number;
  over30Pct: number;
  topThreeValueSharePct: number;
  distinctStarters: number;
  starterMinutesSharePct: number;
  transfermarktAverageAge: number | null;
  transfermarktMarketValueEur: number | null;
  transfermarktSquadSize: number | null;
}

export interface GroupOutcome {
  played: number;
  points: number;
  goalDifference: number;
}

export interface SquadLeader {
  playerId: string;
  name: string;
  position: Position;
  goals: number;
  assists: number;
  minutes: number;
}

export interface ComparedTeam {
  id: string;
  code: string;
  name: string;
  confederation: string;
  groupLetter: string | null;
  managerName: string | null;
  fifaRankingPreTournament: number | null;
  eloRating: number | null;
  standingLabel: string;
  stageCaption: string;
  record: {
    won: number;
    drawn: number;
    lost: number;
    goalsFor: number;
    goalsAgainst: number;
  };
  goalDifference: number;
  rates: TeamRates;
  discipline: TeamDisciplineSummary;
  squad: SquadProfile;
  group: GroupOutcome;
  matchResults: TeamMatchResult[];
  topScorer: SquadLeader | null;
  topAssister: SquadLeader | null;
  mostMinutes: SquadLeader | null;
}

export interface ComparedStat {
  label: string;
  teamADisplay: string;
  teamBDisplay: string;
  fieldDisplay: string;
  teamAValue: number;
  teamBValue: number;
  fieldValue: number;
  higherIsBetter: boolean;
  teamAIsBetter: boolean;
  teamBIsBetter: boolean;
}

export interface SideNote {
  side: "a" | "b";
  kind: "strength" | "flaw";
  label: string;
  detail: string;
}

export interface Meeting {
  matchId: string;
  stage: string;
  teamAScore: number;
  teamBScore: number;
  teamAResult: ResultLetter;
  penaltyScore: string | null;
}

export interface ComparisonPlayer {
  id: string;
  name: string;
  initials: string;
  position: Position;
  club: string;
  age: number;
  heightCm: number;
  marketValueEur: number;
  caps: number;
  appearances: number;
  starts: number;
  minutes: number;
  goals: number;
  assists: number;
  goalsPer90: number;
  assistsPer90: number;
  goalContributionsPer90: number;
  yellowCards: number;
  redCards: number;
  penaltyGoals: number;
  ownGoals: number;
  cleanSheets: number | null;
  saves: number | null;
  goalsConceded: number | null;
  savesPer90: number | null;
  goalsConcededPer90: number | null;
}

export interface PositionRollup {
  minutes: number;
  marketValueEur: number;
  goals: number;
  assists: number;
}

export interface PositionGroup {
  position: Position;
  teamAPlayers: ComparisonPlayer[];
  teamBPlayers: ComparisonPlayer[];
  teamARollup: PositionRollup;
  teamBRollup: PositionRollup;
}

export interface TeamComparison {
  id: string;
  scopeLabel: string;
  teamA: ComparedTeam;
  teamB: ComparedTeam;
  comparedStats: ComparedStat[];
  strengthsAndFlaws: SideNote[];
  meetings: Meeting[];
  positions: PositionGroup[];
}
