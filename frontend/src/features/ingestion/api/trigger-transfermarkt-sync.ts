import { fetchJson } from "@/lib/api/client";

export interface TriggerSyncResult {
  jobId: number;
  status: string;
}

export async function triggerTransfermarktSync(skipPopulated: boolean): Promise<TriggerSyncResult> {
  const payload = await fetchJson<{ job_id: number; status: string }>(
    "/api/admin/ingestion/transfermarkt-sync",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skip_populated: skipPopulated }),
    },
  );
  return { jobId: payload.job_id, status: payload.status };
}
