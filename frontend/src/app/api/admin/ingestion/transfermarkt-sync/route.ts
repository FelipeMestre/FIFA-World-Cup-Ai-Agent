import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `POST /admin/ingestion/transfermarkt-sync`, which queues a
 * roster-scoped Transfermarkt sync job and returns its id to poll.
 */
export async function POST(request: Request) {
  let body: { skip_populated?: unknown } = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  const skipPopulated = typeof body.skip_populated === "boolean" ? body.skip_populated : false;

  return proxyBackendJson("/admin/ingestion/transfermarkt-sync", {
    method: "POST",
    body: JSON.stringify({ skip_populated: skipPopulated }),
  });
}
