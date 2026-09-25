import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `POST /admin/identity-links/rematch`, which wipes every
 * `player_identity_link` row and queues a from-scratch regeneration job.
 * `confirm: true` is always sent here, never taken from the request body --
 * the UI's own confirmation dialog is the actual gate on calling this route
 * at all, so there's no client-supplied flag to trust or distrust.
 */
export async function POST() {
  return proxyBackendJson("/admin/identity-links/rematch", {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
}
