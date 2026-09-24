import { describe, expect, it } from "vitest";

import {
  identityLinkReviewSchema,
  toIdentityLinkReview,
} from "@/features/identity-links/schemas/identity-link-review.schema";

function baseWireRow() {
  return {
    id: 1,
    match_method: "fuzzy_name" as const,
    match_confidence: "0.870",
    status: "pending" as const,
    created_at: "2026-09-24T17:18:05.036056Z",
    synthetic_player: {
      id: 500,
      team_id: 1,
      name: "Test Player",
      nationality: "Testland",
      position: "FW",
      club_team: "Test Club",
      market_value_eur: 1000000,
      caps: 10,
      date_of_birth: "2000-01-01",
      height_cm: 180,
      goals: 5,
    },
    real_player: {
      player_id: 990601,
      first_name: "Real",
      last_name: "Player",
      date_of_birth: null,
      country_of_birth: null,
      country_of_citizenship: null,
      position: "Forward",
      sub_position: null,
      foot: null,
      height_cm: null,
      current_club_id: null,
      current_national_team_id: null,
      international_caps: null,
      international_goals: null,
      market_value_eur: null,
      highest_market_value_eur: null,
      profile_url: "https://example.test/player",
    },
  };
}

describe("identityLinkReviewSchema / toIdentityLinkReview", () => {
  it("parses the backend's string-encoded Decimal confidence into a number", () => {
    const row = identityLinkReviewSchema.parse(baseWireRow());

    expect(toIdentityLinkReview(row).matchConfidence).toBe(0.87);
  });

  it("keeps a manual match's null confidence as null, not NaN", () => {
    const row = identityLinkReviewSchema.parse({
      ...baseWireRow(),
      match_method: "manual",
      match_confidence: null,
    });

    expect(toIdentityLinkReview(row).matchConfidence).toBeNull();
  });

  it("maps both sides' snake_case fields to the camelCase domain shape", () => {
    const row = identityLinkReviewSchema.parse(baseWireRow());

    const review = toIdentityLinkReview(row);

    expect(review.syntheticPlayer).toMatchObject({
      id: 500,
      teamId: 1,
      nationality: "Testland",
      clubTeam: "Test Club",
      marketValueEur: 1000000,
      dateOfBirth: "2000-01-01",
      heightCm: 180,
    });
    expect(review.realPlayer).toMatchObject({
      playerId: 990601,
      firstName: "Real",
      lastName: "Player",
      profileUrl: "https://example.test/player",
    });
  });
});
