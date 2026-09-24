import { describe, expect, it } from "vitest";

import {
  clubProfileFacts,
  formatTransferFee,
  formatTransferMonth,
  formatTransferValue,
} from "@/features/chat/components/player-club-format";
import type { PlayerClubProfile } from "@/features/chat/types";

const profile: PlayerClubProfile = {
  preferredFoot: "right",
  subPosition: "Centre-Forward",
  heightCm: 178,
  dateOfBirth: "1998-12-20",
  citizenship: "France",
  currentClub: "Real Madrid",
  marketValueEur: 180_000_000,
  highestMarketValueEur: 200_000_000,
  internationalCaps: 85,
  internationalGoals: 48,
};

describe("clubProfileFacts", () => {
  it("formats the Transfermarkt profile for the widget", () => {
    expect(clubProfileFacts(profile)).toEqual([
      { label: "Preferred foot", value: "Right" },
      { label: "Sub-position", value: "Centre-Forward" },
      { label: "Height", value: "178 cm" },
      { label: "Date of birth", value: "20 Dec 1998" },
      { label: "Citizenship", value: "France" },
      { label: "Current club", value: "Real Madrid" },
      { label: "Market value", value: "€180M" },
      { label: "Career high", value: "€200M" },
      { label: "International caps", value: "85" },
      { label: "International goals", value: "48" },
    ]);
  });

  it("drops fields the link did not provide", () => {
    const sparse: PlayerClubProfile = {
      ...profile,
      preferredFoot: null,
      currentClub: null,
      marketValueEur: null,
      internationalGoals: 0,
    };

    const labels = clubProfileFacts(sparse).map((fact) => fact.label);

    expect(labels).not.toContain("Preferred foot");
    expect(labels).not.toContain("Current club");
    expect(labels).not.toContain("Market value");
    expect(labels).toContain("International goals");
  });
});

describe("transfer table cells", () => {
  it("shows month and year, a free move, and the value", () => {
    expect(formatTransferMonth("2024-07-01")).toBe("Jul 2024");
    expect(formatTransferMonth("2017-08-31")).toBe("Aug 2017");
    expect(formatTransferFee(null)).toBe("—");
    expect(formatTransferFee(0)).toBe("Free");
    expect(formatTransferFee(180_000_000)).toBe("€180M");
    expect(formatTransferValue(180_000_000)).toBe("€180M");
    expect(formatTransferValue(null)).toBe("—");
  });
});
