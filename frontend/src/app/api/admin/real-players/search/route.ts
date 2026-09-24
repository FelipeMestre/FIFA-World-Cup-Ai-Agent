import { NextResponse } from "next/server";

import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

// Mirrors the backend's `q: Query(min_length=2)` -- a shorter query returns
// no results without a round trip (the backend would 422 it anyway).
const MIN_QUERY_LENGTH = 2;

/** Proxies `GET /admin/real-players/search` -- backs the identity-link
 * "correct match" picker.
 */
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const query = params.get("q")?.trim();
  if (!query || query.length < MIN_QUERY_LENGTH) {
    return NextResponse.json([]);
  }
  const limit = params.get("limit") ?? "20";

  return proxyBackendJson(
    `/admin/real-players/search?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`,
  );
}
