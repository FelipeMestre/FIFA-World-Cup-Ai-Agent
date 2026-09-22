import type { PlayerComparison } from "@/features/chat/types";

/**
 * Illustrative sample data (design/README.md), sourced from
 * WidgetCompare.dc.html's 4-row headline set and PanelCompare.dc.html's
 * full 10-row breakdown -- both stored here in `rows`; the widget picks its
 * 4 headline rows by label (see widget-compare.tsx).
 */

interface RawComparisonRow {
  label: string;
  note?: string;
  a: number;
  b: number;
  /** Raw (non minutes-normalized) totals; defaults to `a`/`b` when omitted (e.g. already-total rows like Minutes). */
  totalA?: number;
  totalB?: number;
  aPercentile?: number;
  bPercentile?: number;
  lowerIsBetter?: boolean;
  displayA?: string;
  displayB?: string;
  suppressMark?: boolean;
}

const COMPARISON_ROWS: RawComparisonRow[] = [
  { label: "Goals", a: 0.75, b: 0.88, totalA: 5, totalB: 6, aPercentile: 88, bPercentile: 94 },
  { label: "Assists", a: 0.6, b: 0.29, totalA: 4, totalB: 2, aPercentile: 97, bPercentile: 72 },
  {
    label: "Goals + assists",
    a: 1.35,
    b: 1.18,
    totalA: 9,
    totalB: 8,
    aPercentile: 96,
    bPercentile: 91,
  },
  { label: "Shots", a: 3.61, b: 4.26, totalA: 24, totalB: 29, aPercentile: 79, bPercentile: 90 },
  {
    label: "Shots on target",
    a: 1.81,
    b: 2.06,
    totalA: 12,
    totalB: 14,
    aPercentile: 84,
    bPercentile: 92,
  },
  {
    label: "Shot accuracy",
    note: "On target ÷ shots",
    a: 50.0,
    b: 48.3,
    aPercentile: 70,
    bPercentile: 66,
    displayA: "50.0%",
    displayB: "48.3%",
  },
  {
    label: "Fouls committed",
    note: "Lower is better",
    a: 0.45,
    b: 0.74,
    totalA: 3,
    totalB: 5,
    aPercentile: 71,
    bPercentile: 58,
    lowerIsBetter: true,
  },
  {
    label: "Offsides",
    note: "Lower is better",
    a: 0.3,
    b: 0.59,
    totalA: 2,
    totalB: 4,
    aPercentile: 80,
    bPercentile: 62,
    lowerIsBetter: true,
  },
  {
    label: "Yellow cards",
    note: "Lower is better",
    a: 0.15,
    b: 0.15,
    totalA: 1,
    totalB: 1,
    lowerIsBetter: true,
  },
  {
    label: "Minutes",
    note: "Total",
    a: 598,
    b: 612,
    displayA: "598",
    displayB: "612",
    suppressMark: true,
  },
];

function toComparisonRow(row: RawComparisonRow) {
  const totalA = row.totalA ?? row.a;
  const totalB = row.totalB ?? row.b;
  const aBetter = row.suppressMark
    ? false
    : row.lowerIsBetter
      ? row.a < row.b
      : row.a > row.b;
  const bBetter = row.suppressMark
    ? false
    : row.lowerIsBetter
      ? row.b < row.a
      : row.b > row.a;
  const totalABetter = row.suppressMark
    ? false
    : row.lowerIsBetter
      ? totalA < totalB
      : totalA > totalB;
  const totalBBetter = row.suppressMark
    ? false
    : row.lowerIsBetter
      ? totalB < totalA
      : totalB > totalA;
  const fmt = (n: number, display?: string) => display ?? n.toFixed(2);
  return {
    label: row.label,
    note: row.note,
    playerAPerNinety: fmt(row.a, row.displayA),
    playerBPerNinety: fmt(row.b, row.displayB),
    playerATotal: row.displayA ?? String(totalA),
    playerBTotal: row.displayB ?? String(totalB),
    playerAIsBetter: aBetter,
    playerBIsBetter: bBetter,
    playerATotalIsBetter: totalABetter,
    playerBTotalIsBetter: totalBBetter,
    playerAPercentile: row.aPercentile,
    playerBPercentile: row.bPercentile,
  };
}

export const sampleComparison: PlayerComparison = {
  id: "compare-messi-mbappe",
  normalization: "per90",
  scopeLabel: "Per 90 · forwards",
  playerA: { id: "player-messi", initials: "LM", name: "Lionel Messi", teamCode: "ARG", position: "FWD", minutes: 598 },
  playerB: { id: "player-mbappe", initials: "KM", name: "Kylian Mbappé", teamCode: "FRA", position: "FWD", minutes: 612 },
  rows: COMPARISON_ROWS.map(toComparisonRow),
  insights: [
    "Messi: 97th percentile for assists per 90 among forwards",
    "Mbappé: 94th percentile for goals per 90 among forwards",
  ],
  minMinutesCaption: "Min. 270 minutes to rank",
};
