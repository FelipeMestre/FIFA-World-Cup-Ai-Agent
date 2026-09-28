import type { EntityOption } from "@/features/chat/components/entity-chip-selector";
import { fetchJson } from "@/lib/api/client";

interface MatchSearchResultDto {
  id: number;
  date: string;
  home_team_id: number;
  home_team_name: string;
  away_team_id: number;
  away_team_name: string;
  home_score: number;
  away_score: number;
  status: string;
}

/** `GET /api/matches/search?q=` via our own Next.js proxy route -- backs the
 * chat composer's Match chip. No pagination: the whole tournament is ~100
 * matches, so a filtered result set is always small.
 */
export async function searchMatches(query: string): Promise<EntityOption[]> {
  const results = await fetchJson<MatchSearchResultDto[]>(
    `/api/matches/search?q=${encodeURIComponent(query)}`,
  );
  return results.map((match) => ({
    id: String(match.id),
    name: `${match.home_team_name} vs ${match.away_team_name} — ${match.date}`,
  }));
}
