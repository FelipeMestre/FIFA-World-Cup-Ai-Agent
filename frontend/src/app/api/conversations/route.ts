import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `GET /conversations` for the signed-in user's sidebar list. */
export async function GET() {
  return proxyBackendJson("/conversations");
}
