import { NextResponse } from "next/server";

import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `GET /admin/real-players/search` -- backs the identity-link
 * "correct match" picker. An empty/missing query returns no results
 * without a round trip to the backend (which requires a non-empty `q`).
 */
export async function GET(request: Request) {
  const query = new URL(request.url).searchParams.get("q")?.trim();
  if (!query) {
    return NextResponse.json([]);
  }

  return proxyBackendJson(`/admin/real-players/search?q=${encodeURIComponent(query)}`);
}
