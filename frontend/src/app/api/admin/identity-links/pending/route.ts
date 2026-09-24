import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `GET /admin/identity-links/pending` for the admin review list. */
export async function GET() {
  return proxyBackendJson("/admin/identity-links/pending");
}
