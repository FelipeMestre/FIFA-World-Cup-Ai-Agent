import { NextResponse } from "next/server";

import { isIngestionJobId } from "@/features/ingestion/ingestion-job-id";
import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `GET /admin/ingestion/jobs/{id}` -- the endpoint the sync-jobs
 * panel's refresh button polls for status and current stage.
 */
export async function GET(request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  if (!isIngestionJobId(jobId)) {
    return NextResponse.json({ detail: "Ingestion job not found" }, { status: 404 });
  }

  return proxyBackendJson(`/admin/ingestion/jobs/${jobId}`);
}
