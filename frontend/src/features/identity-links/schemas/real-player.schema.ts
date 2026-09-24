import { z } from "zod";

import type { RealPlayerSummary } from "@/features/identity-links/types";

/** Mirrors `RealPlayerSummary` (backend DTO) -- shared by the identity-link
 * review response and the real-player search endpoint.
 */
export const realPlayerSummarySchema = z.object({
  player_id: z.number().int(),
  first_name: z.string(),
  last_name: z.string(),
  date_of_birth: z.string().nullable(),
  country_of_birth: z.string().nullable(),
  country_of_citizenship: z.string().nullable(),
  position: z.string(),
  sub_position: z.string().nullable(),
  foot: z.string().nullable(),
  height_cm: z.number().int().nullable(),
  current_club_id: z.number().int().nullable(),
  current_national_team_id: z.number().int().nullable(),
  international_caps: z.number().int().nullable(),
  international_goals: z.number().int().nullable(),
  market_value_eur: z.number().int().nullable(),
  highest_market_value_eur: z.number().int().nullable(),
  profile_url: z.string(),
});

export const realPlayerSummaryListSchema = z.array(realPlayerSummarySchema);

export function toRealPlayerSummary(
  row: z.infer<typeof realPlayerSummarySchema>,
): RealPlayerSummary {
  return {
    playerId: row.player_id,
    firstName: row.first_name,
    lastName: row.last_name,
    dateOfBirth: row.date_of_birth,
    countryOfBirth: row.country_of_birth,
    countryOfCitizenship: row.country_of_citizenship,
    position: row.position,
    subPosition: row.sub_position,
    foot: row.foot,
    heightCm: row.height_cm,
    currentClubId: row.current_club_id,
    currentNationalTeamId: row.current_national_team_id,
    internationalCaps: row.international_caps,
    internationalGoals: row.international_goals,
    marketValueEur: row.market_value_eur,
    highestMarketValueEur: row.highest_market_value_eur,
    profileUrl: row.profile_url,
  };
}
