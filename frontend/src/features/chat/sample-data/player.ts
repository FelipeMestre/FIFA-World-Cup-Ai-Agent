import type { PlayerSummary } from "@/features/chat/types";

/**
 * Illustrative sample data (design/README.md). WidgetPlayer.dc.html's own
 * artboard is titled "role tweak: goalkeeper", so the goalkeeper variant
 * (Emiliano Martínez) is its canonical sample; PanelPlayer.dc.html's
 * `renderVals()` is hardcoded to a forward (Kylian Mbappé) instead -- both
 * kept here, matching each artboard's own source data exactly.
 */

export const samplePlayerGoalkeeper: PlayerSummary = {
  id: "player-martinez",
  name: "Emiliano Martínez",
  initials: "EM",
  teamCode: "ARG",
  position: "GK",
  appearances: 7,
  minutes: 630,
  scopeLabel: "7 apps · 630 min",
  tierLabel: "Shot-stopping: high · top 20%",
  tierSegments: 2,
  disciplineLabel: "Discipline: clean",
  chips: [
    { label: "Saves", value: "21" },
    { label: "Clean sheets", value: "3" },
    { label: "Conceded", value: "5" },
    { label: "Minutes", value: "630" },
  ],
  footerCaption: "Save rate 80.8% · 30 shots on target faced",
  fullBreakdown: [
    { stat: "Appearances", total: "7", perNinety: "—" },
    { stat: "Minutes", total: "630", perNinety: "—" },
    { stat: "Saves", total: "21", perNinety: "3.00", percentile: 82 },
    { stat: "Clean sheets", total: "3", perNinety: "0.43", percentile: 78 },
    { stat: "Goals conceded", total: "5", perNinety: "0.71", percentile: 74 },
  ],
  perNinetyVsPositionAverage: [
    { label: "Saves", value: 3.0, positionAverage: 2.1 },
    { label: "Conceded", value: 0.71, positionAverage: 1.15 },
  ],
};

export const samplePlayerForward: PlayerSummary = {
  id: "player-mbappe",
  name: "Kylian Mbappé",
  initials: "KM",
  teamCode: "FRA",
  position: "FWD",
  appearances: 7,
  minutes: 612,
  scopeLabel: "7 apps · 612 min",
  tierLabel: "G+A tier: elite · top 10%",
  tierSegments: 3,
  disciplineLabel: "Discipline: 1 yellow",
  chips: [
    { label: "Goals", value: "6" },
    { label: "Assists", value: "2" },
    { label: "Minutes", value: "612" },
    { label: "Shots", value: "29" },
  ],
  footerCaption: "1.18 goal contributions per 90",
  fullBreakdown: [
    { stat: "Appearances", total: "7", perNinety: "—" },
    { stat: "Minutes", total: "612", perNinety: "—" },
    { stat: "Goals", total: "6", perNinety: "0.88", percentile: 94 },
    { stat: "Assists", total: "2", perNinety: "0.29", percentile: 72 },
    { stat: "Goals + assists", total: "8", perNinety: "1.18", percentile: 91 },
    { stat: "Shots", total: "29", perNinety: "4.26", percentile: 90 },
    { stat: "Shots on target", total: "14", perNinety: "2.06", percentile: 92 },
    { stat: "Fouls committed", total: "5", perNinety: "0.74", percentile: 58 },
    { stat: "Offsides", total: "4", perNinety: "0.59", percentile: 62 },
    { stat: "Yellow cards", total: "1", perNinety: "0.15" },
    { stat: "Red cards", total: "0", perNinety: "0.00" },
  ],
  perNinetyVsPositionAverage: [
    { label: "Goals", value: 0.88, positionAverage: 0.41 },
    { label: "Assists", value: 0.29, positionAverage: 0.18 },
    { label: "Shots", value: 4.26, positionAverage: 2.7 },
    { label: "On target", value: 2.06, positionAverage: 1.05 },
    { label: "Fouls", value: 0.74, positionAverage: 1.1 },
    { label: "Offsides", value: 0.59, positionAverage: 0.45 },
  ],
};
