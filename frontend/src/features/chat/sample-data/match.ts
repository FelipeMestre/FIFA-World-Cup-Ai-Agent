import type { MatchSummary } from "@/features/chat/types";

/**
 * Illustrative sample data (design/README.md), sourced from
 * WidgetMatch.dc.html + PanelMatch.dc.html's own `renderVals()` scripts.
 * Match: France 1-2 Spain (semifinal).
 */

function statRow(label: string, home: number, away: number, homeDisplay?: string, awayDisplay?: string) {
  const total = home + away;
  return {
    label,
    homeValue: homeDisplay ?? String(home),
    awayValue: awayDisplay ?? String(away),
    homePct: total ? Math.round((home / total) * 100) : 50,
  };
}

export const sampleMatch: MatchSummary = {
  id: "match-fra-esp-sf",
  stageLabel: "Semifinal",
  dateLabel: "Jul 14, 2026",
  venueLabel: "AT&T Stadium, Arlington",
  homeTeam: { code: "FRA", name: "France" },
  awayTeam: { code: "ESP", name: "Spain" },
  homeScore: 1,
  awayScore: 2,
  statusLabel: "Full time",
  homeScorers: "Mbappé 51'",
  awayScorers: "Yamal 23' · Oyarzabal 78'",
  stats: [
    statRow("Possession", 44, 56, "44%", "56%"),
    statRow("Shots", 11, 16),
    statRow("On target", 4, 7),
    statRow("Corners", 5, 6),
    statRow("Fouls", 13, 10),
    statRow("Offsides", 2, 1),
    statRow("Yellow cards", 2, 1),
    statRow("Red cards", 0, 0),
  ],
  events: [
    { minute: "23'", kind: "goal", teamCode: "ESP", title: "Lamine Yamal" },
    { minute: "51'", kind: "goal", teamCode: "FRA", title: "Kylian Mbappé" },
    { minute: "78'", kind: "goal", teamCode: "ESP", title: "Mikel Oyarzabal" },
  ],
  playerOfMatch: {
    name: "Lamine Yamal",
    teamCode: "ESP",
    position: "FWD",
    note: "Spain · FWD · 1 goal",
  },
  timeline: [
    { minute: "23'", kind: "goal", teamCode: "ESP", title: "Goal · Lamine Yamal", detail: "Assist Pedri · FRA 0–1 ESP" },
    { minute: "31'", kind: "card", teamCode: "FRA", title: "Yellow card · Aurélien Tchouéméni", detail: "Foul" },
    { minute: "38'", kind: "var", teamCode: "FRA", title: "VAR review · penalty check", detail: "Challenge on Dembélé · no penalty" },
    { minute: "51'", kind: "goal", teamCode: "FRA", title: "Goal · Kylian Mbappé", detail: "Assist Michael Olise · FRA 1–1 ESP" },
    { minute: "64'", kind: "sub", teamCode: "FRA", title: "Substitution", subOn: "Eduardo Camavinga", subOff: "N'Golo Kanté" },
    { minute: "64'", kind: "sub", teamCode: "ESP", title: "Substitution", subOn: "Mikel Oyarzabal", subOff: "Álvaro Morata" },
    { minute: "72'", kind: "card", teamCode: "ESP", title: "Yellow card · Rodri", detail: "Tactical foul" },
    { minute: "72'", kind: "sub", teamCode: "FRA", title: "Substitution", subOn: "Bradley Barcola", subOff: "Ousmane Dembélé" },
    { minute: "78'", kind: "goal", teamCode: "ESP", title: "Goal · Mikel Oyarzabal", detail: "Assist Nico Williams · FRA 1–2 ESP" },
    { minute: "80'", kind: "sub", teamCode: "ESP", title: "Substitution", subOn: "Mikel Merino", subOff: "Pedri" },
    { minute: "88'", kind: "sub", teamCode: "ESP", title: "Substitution", subOn: "Martín Zubimendi", subOff: "Fabián Ruiz" },
    { minute: "90+3'", kind: "card", teamCode: "FRA", title: "Yellow card · Dayot Upamecano", detail: "Dissent" },
  ],
  lineups: [
    {
      code: "FRA",
      name: "France",
      shape: "4-3-3",
      groups: [
        { name: "GK", players: [{ number: 16, name: "Mike Maignan" }] },
        {
          name: "DEF",
          players: [
            { number: 5, name: "Jules Koundé" },
            { number: 17, name: "William Saliba" },
            { number: 4, name: "Dayot Upamecano" },
            { number: 22, name: "Theo Hernández" },
          ],
        },
        {
          name: "MID",
          players: [
            { number: 8, name: "Aurélien Tchouéméni" },
            { number: 14, name: "Adrien Rabiot" },
            { number: 13, name: "N'Golo Kanté", mark: "▼ 64'" },
          ],
        },
        {
          name: "FWD",
          players: [
            { number: 11, name: "Ousmane Dembélé", mark: "▼ 72'" },
            { number: 10, name: "Kylian Mbappé" },
            { number: 7, name: "Michael Olise" },
          ],
        },
        {
          name: "Subs used",
          players: [
            { number: 6, name: "Eduardo Camavinga", mark: "▲ 64'" },
            { number: 20, name: "Bradley Barcola", mark: "▲ 72'" },
          ],
        },
      ],
    },
    {
      code: "ESP",
      name: "Spain",
      shape: "4-3-3",
      groups: [
        { name: "GK", players: [{ number: 23, name: "Unai Simón" }] },
        {
          name: "DEF",
          players: [
            { number: 2, name: "Dani Carvajal" },
            { number: 3, name: "Robin Le Normand" },
            { number: 14, name: "Aymeric Laporte" },
            { number: 24, name: "Marc Cucurella" },
          ],
        },
        {
          name: "MID",
          players: [
            { number: 16, name: "Rodri" },
            { number: 8, name: "Pedri", mark: "▼ 80'" },
            { number: 20, name: "Fabián Ruiz", mark: "▼ 88'" },
          ],
        },
        {
          name: "FWD",
          players: [
            { number: 19, name: "Lamine Yamal" },
            { number: 7, name: "Álvaro Morata", mark: "▼ 64'" },
            { number: 17, name: "Nico Williams" },
          ],
        },
        {
          name: "Subs used",
          players: [
            { number: 21, name: "Mikel Oyarzabal", mark: "▲ 64'" },
            { number: 6, name: "Mikel Merino", mark: "▲ 80'" },
            { number: 18, name: "Martín Zubimendi", mark: "▲ 88'" },
          ],
        },
      ],
    },
  ],
  footerCaption: "3 goals · 3 cards · 1 VAR review",
};
