import { fetchJson } from "@/lib/api/client";
import {
  realPlayerSummaryListSchema,
  toRealPlayerSummary,
} from "@/features/identity-links/schemas/real-player.schema";
import type { RealPlayerSummary } from "@/features/identity-links/types";

export async function searchRealPlayers(
  query: string,
  limit: number = 20,
): Promise<RealPlayerSummary[]> {
  const payload = await fetchJson<unknown>(
    `/api/admin/real-players/search?q=${encodeURIComponent(query)}&limit=${limit}`,
  );
  return realPlayerSummaryListSchema.parse(payload).map(toRealPlayerSummary);
}
