import { fetchJson } from "@/lib/api/client";
import { jobStatusSchema, toJobStatus } from "@/features/ingestion/schemas/job-status.schema";
import type { JobStatus } from "@/features/ingestion/types";

export async function getJobStatus(jobId: number): Promise<JobStatus> {
  const payload = await fetchJson<unknown>(`/api/admin/ingestion/jobs/${jobId}`);
  return toJobStatus(jobStatusSchema.parse(payload));
}
