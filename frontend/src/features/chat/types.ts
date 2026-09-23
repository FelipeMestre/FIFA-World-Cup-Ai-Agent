/**
 * Widget contract from design/README.md. The backend sends structured
 * "parts"; the renderer maps each to a component. Only `type: "text"` is
 * actually sent by the live backend today -- the other four widget/panel
 * data shapes are defined here from the illustrative sample data in each
 * artboard's `renderVals()` script (design/artboards/Widget*.dc.html,
 * Panel*.dc.html), for forward-compat with a future analytics-tool phase.
 */

export type ResultLetter = "W" | "D" | "L";

/** design/README.md's hard data-limit rule: positions only GK/DEF/MID/FWD. */
export type Position = "GK" | "DEF" | "MID" | "FWD";

export interface EntityRef {
  type: "team" | "match" | "player" | "compare";
  id: string;
}

// ---------------------------------------------------------------------------
// Team

export interface TeamMatchResult {
  stage: string;
  opponentCode: string;
  opponentName: string;
  score: string;
  result: ResultLetter;
}

export interface TeamGoalsByMatch {
  opponentCode: string;
  goalsFor: number;
  goalsAgainst: number;
}

export interface StatWithFieldAverage {
  label: string;
  value: string;
  fieldValue: string;
  /** e.g. "▲ 8.4" or "▼ 1.2" -- always carries the glyph, never color alone. */
  delta: string;
}

export interface TeamSummary {
  id: string;
  code: string;
  name: string;
  scopeLabel: string;
  standingLabel: string;
  record: {
    won: number;
    drawn: number;
    lost: number;
    goalsFor: number;
    goalsAgainst: number;
  };
  goalDifference: number;
  concededPerGame: number;
  cleanSheets: number;
  avgPossessionPct: number;
  goalsByMatch: TeamGoalsByMatch[];
  tournamentAverages: StatWithFieldAverage[];
  matchResults: TeamMatchResult[];
  discipline: {
    yellowCards: number;
    redCards: number;
    fouls: number;
    yellowPerMatch: number;
    fieldYellowPerMatch: number;
  };
  stageCaption: string;
}

// ---------------------------------------------------------------------------
// Match

export interface MatchStatRow {
  label: string;
  homeValue: string;
  awayValue: string;
  /** Home share of the split bar, 0-100. */
  homePct: number;
}

export type MatchEventKind = "goal" | "card" | "var" | "sub";

export interface MatchEvent {
  minute: string;
  kind: MatchEventKind;
  teamCode: string;
  title: string;
  detail?: string;
  subOn?: string;
  subOff?: string;
}

export interface LineupPlayer {
  number: number;
  name: string;
  /** e.g. "▲ 64'" (on) or "▼ 72'" (off); undefined when not substituted. */
  mark?: string;
}

export interface LineupGroup {
  name: Position | "Subs used";
  players: LineupPlayer[];
}

export interface TeamLineup {
  code: string;
  name: string;
  shape: string;
  groups: LineupGroup[];
}

export interface MatchSummary {
  id: string;
  stageLabel: string;
  dateLabel: string;
  venueLabel?: string;
  homeTeam: { code: string; name: string };
  awayTeam: { code: string; name: string };
  homeScore: number;
  awayScore: number;
  statusLabel: string;
  homeScorers: string;
  awayScorers: string;
  stats: MatchStatRow[];
  events: MatchEvent[];
  playerOfMatch: {
    name: string;
    teamCode: string;
    position: Position;
    note: string;
  };
  timeline: MatchEvent[];
  lineups: TeamLineup[];
  footerCaption: string;
}

// ---------------------------------------------------------------------------
// Player

export interface StatChip {
  label: string;
  value: string;
}

export interface PlayerStatRow {
  stat: string;
  total: string;
  perNinety: string;
  /** Percentile within position; `null` for stats with no percentile (e.g. minutes) -- the wire value, not `undefined` (backend sends the key with a JSON `null`, never omits it). */
  percentile: number | null;
}

export interface PlayerBenchmarkRow {
  label: string;
  value: number;
  positionAverage: number;
}

export interface PlayerSummary {
  id: string;
  name: string;
  initials: string;
  teamCode: string;
  position: Position;
  appearances: number;
  minutes: number;
  scopeLabel: string;
  tierLabel: string;
  /** Filled segments of the 3-step contribution meter, 0-3. */
  tierSegments: number;
  disciplineLabel: string;
  chips: StatChip[];
  footerCaption: string;
  fullBreakdown: PlayerStatRow[];
  perNinetyVsPositionAverage: PlayerBenchmarkRow[];
}

// ---------------------------------------------------------------------------
// Player comparison

export interface ComparisonPlayerRef {
  id: string;
  initials: string;
  name: string;
  teamCode: string;
  position: Position;
  minutes: number;
}

export interface ComparisonRowData {
  label: string;
  note?: string;
  playerAPerNinety: string;
  playerBPerNinety: string;
  playerATotal: string;
  playerBTotal: string;
  /** Per-90 comparison -- headline/insights basis and what the percentile below is ranked against. */
  playerAIsBetter: boolean;
  playerBIsBetter: boolean;
  /** Raw-total comparison -- can differ in order from the per-90 one above. */
  playerATotalIsBetter: boolean;
  playerBTotalIsBetter: boolean;
  playerAPercentile?: number;
  playerBPercentile?: number;
}

export interface PlayerComparison {
  id: string;
  normalization: "per90" | "totals";
  scopeLabel: string;
  playerA: ComparisonPlayerRef;
  playerB: ComparisonPlayerRef;
  rows: ComparisonRowData[];
  insights: string[];
  minMinutesCaption: string;
}

// ---------------------------------------------------------------------------
// Message parts (the backend's discriminated union)

export type MessagePart =
  | { type: "text"; content: string }
  | { type: "team_widget"; data: TeamSummary }
  | { type: "match_widget"; data: MatchSummary }
  | { type: "player_widget"; data: PlayerSummary }
  | { type: "compare_widget"; data: PlayerComparison };

export type ChatRole = "user" | "assistant";

export interface ConversationSummary {
  id: string;
  title: string;
  updatedAt: string;
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  parts: MessagePart[];
  /** The model's reasoning trace, appended incrementally from `reasoning_delta` events. */
  reasoning?: string;
  /** True while this assistant message is still receiving stream events. */
  isStreaming?: boolean;
  /** Name of the tool the loop is currently dispatching, cleared once resolved. */
  activeToolName?: string;
  /** Set when the tool loop's iteration cap tripped; rendered as a distinct inline note. */
  clarification?: string;
  /** Set on an assistant message that failed to send/receive a reply. */
  error?: string;
}

// ---------------------------------------------------------------------------
// Side panel state (design/README.md's "Panel behavior")

export interface PanelState {
  openEntity: EntityRef | null;
  collapsed: boolean;
  sourceMessageId: string | null;
}
