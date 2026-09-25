import { fetchJson } from "@/lib/api/client";

export interface TriggerRematchResult {
  jobId: number;
  status: string;
}

/** Triggers `POST /admin/identity-links/rematch` -- wipes and regenerates
 * every `player_identity_link` row from the current rosters. The UI's own
 * confirmation dialog is the gate for calling this at all; the Route
 * Handler always sends `confirm: true` once it's called.
 */
export async function triggerIdentityLinkRematch(): Promise<TriggerRematchResult> {
  const payload = await fetchJson<{ job_id: number; status: string }>(
    "/api/admin/identity-links/rematch",
    { method: "POST" },
  );
  return { jobId: payload.job_id, status: payload.status };
}
