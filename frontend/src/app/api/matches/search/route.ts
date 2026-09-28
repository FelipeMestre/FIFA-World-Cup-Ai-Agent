import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `GET /matches/search` -- backs the chat composer's Match chip.
 * An empty `q` is forwarded as-is (the backend returns every match for it),
 * so the chip can list all matches before the user types anything. No
 * `limit` param: the whole tournament is ~100 matches and the backend
 * doesn't paginate this endpoint.
 */
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const query = params.get("q")?.trim() ?? "";

  return proxyBackendJson(`/matches/search?q=${encodeURIComponent(query)}`);
}
