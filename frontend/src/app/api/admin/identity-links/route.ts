import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `GET /admin/identity-links` for the admin review list, forwarding
 * `status`/`limit`/`offset` for filtering and pagination.
 */
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const status = params.get("status");
  const limit = params.get("limit");
  const offset = params.get("offset");

  const query = new URLSearchParams();
  if (status !== null) query.set("status", status);
  if (limit !== null) query.set("limit", limit);
  if (offset !== null) query.set("offset", offset);
  const queryString = query.toString();

  return proxyBackendJson(`/admin/identity-links${queryString ? `?${queryString}` : ""}`);
}
