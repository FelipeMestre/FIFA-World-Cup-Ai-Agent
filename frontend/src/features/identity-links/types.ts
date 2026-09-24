/** The synthetic WC2026 roster side of a proposed identity-link match. */
export interface SyntheticPlayerSummary {
  id: number;
  teamId: number;
  name: string;
  /** The WC2026 national team's country name (e.g. "Brazil"). */
  nationality: string;
  position: string;
  clubTeam: string;
  marketValueEur: number;
  caps: number;
  dateOfBirth: string;
  heightCm: number;
  goals: number;
}

/** The Transfermarkt side -- also what the real-player search endpoint
 * returns for the "correct match" picker.
 */
export interface RealPlayerSummary {
  playerId: number;
  firstName: string;
  lastName: string;
  dateOfBirth: string | null;
  countryOfBirth: string | null;
  countryOfCitizenship: string | null;
  position: string;
  subPosition: string | null;
  foot: string | null;
  heightCm: number | null;
  currentClubId: number | null;
  currentNationalTeamId: number | null;
  internationalCaps: number | null;
  internationalGoals: number | null;
  marketValueEur: number | null;
  highestMarketValueEur: number | null;
  profileUrl: string;
}

export type MatchMethod = "exact_name_dob" | "exact_name_team" | "fuzzy_name" | "manual";

export type IdentityLinkReviewStatus = "pending" | "approved" | "rejected";

export interface IdentityLinkReview {
  id: number;
  matchMethod: MatchMethod;
  /** 0-1, `null` for a manual (admin-corrected) match. */
  matchConfidence: number | null;
  status: IdentityLinkReviewStatus;
  createdAt: string | null;
  syntheticPlayer: SyntheticPlayerSummary;
  realPlayer: RealPlayerSummary;
}

/** One page of the pending-review queue, plus the total count needed to
 * render a paginator (the page's own item count alone can't say how many
 * pages exist).
 */
export interface PendingIdentityLinksPage {
  items: IdentityLinkReview[];
  total: number;
  limit: number;
  offset: number;
}
