import { z } from "zod";

import {
  realPlayerSummarySchema,
  toRealPlayerSummary,
} from "@/features/identity-links/schemas/real-player.schema";
import type {
  IdentityLinkReview,
  MatchMethod,
  PendingIdentityLinksPage,
} from "@/features/identity-links/types";

const matchMethodSchema = z.enum(["exact_name_dob", "exact_name_team", "fuzzy_name", "manual"]);
const reviewStatusSchema = z.enum(["pending", "approved", "rejected"]);

const syntheticPlayerSchema = z.object({
  id: z.number().int(),
  team_id: z.number().int(),
  name: z.string(),
  nationality: z.string(),
  position: z.string(),
  club_team: z.string(),
  market_value_eur: z.number().int(),
  caps: z.number().int(),
  date_of_birth: z.string(),
  height_cm: z.number().int(),
  goals: z.number().int(),
});

/** `match_confidence` is a backend `Decimal`, which FastAPI/Pydantic
 * serializes as a JSON string (e.g. `"0.870"`), not a number -- preserving
 * precision rather than risking float rounding.
 */
export const identityLinkReviewSchema = z.object({
  id: z.number().int(),
  match_method: matchMethodSchema,
  match_confidence: z.string().nullable(),
  status: reviewStatusSchema,
  created_at: z.string().nullable(),
  synthetic_player: syntheticPlayerSchema,
  real_player: realPlayerSummarySchema,
});

export const identityLinkReviewListSchema = z.array(identityLinkReviewSchema);

export const pendingIdentityLinksPageSchema = z.object({
  items: identityLinkReviewListSchema,
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});

export function toPendingIdentityLinksPage(
  row: z.infer<typeof pendingIdentityLinksPageSchema>,
): PendingIdentityLinksPage {
  return {
    items: row.items.map(toIdentityLinkReview),
    total: row.total,
    limit: row.limit,
    offset: row.offset,
  };
}

export function toIdentityLinkReview(
  row: z.infer<typeof identityLinkReviewSchema>,
): IdentityLinkReview {
  return {
    id: row.id,
    matchMethod: row.match_method as MatchMethod,
    matchConfidence: row.match_confidence === null ? null : Number(row.match_confidence),
    status: row.status,
    createdAt: row.created_at,
    syntheticPlayer: {
      id: row.synthetic_player.id,
      teamId: row.synthetic_player.team_id,
      name: row.synthetic_player.name,
      nationality: row.synthetic_player.nationality,
      position: row.synthetic_player.position,
      clubTeam: row.synthetic_player.club_team,
      marketValueEur: row.synthetic_player.market_value_eur,
      caps: row.synthetic_player.caps,
      dateOfBirth: row.synthetic_player.date_of_birth,
      heightCm: row.synthetic_player.height_cm,
      goals: row.synthetic_player.goals,
    },
    realPlayer: toRealPlayerSummary(row.real_player),
  };
}
