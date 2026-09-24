import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `GET /auth/me` for the signed-in user's display profile. */
export async function GET() {
  return proxyBackendJson("/auth/me");
}
