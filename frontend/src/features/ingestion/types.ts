export type IngestionJobType =
  | "synthetic_upload"
  | "transfermarkt_sync"
  | "bulk_synthetic_upload"
  | "identity_link_rematch";

export type IngestionJobStatus = "queued" | "running" | "succeeded" | "failed";

export interface StageCheckpoint {
  stage: string;
  completedAt: string;
}

export interface JobStatus {
  jobId: number;
  jobType: IngestionJobType;
  status: IngestionJobStatus;
  rowCounts: Record<string, number>;
  errorMessage: string | null;
  currentStage: string | null;
  stageCheckpoints: StageCheckpoint[];
  /** Every stage a `transfermarkt_sync` job's pipeline goes through, in
   * order -- empty for a `synthetic_upload` job, which has no sub-stages.
   */
  allStages: string[];
}

/** One uploaded file's outcome from `POST /admin/ingestion/bulk-synthetic-upload`.
 * `tableName`/`reason` are mutually exclusive depending on `accepted`. This
 * per-file breakdown only exists in that response -- it is never part of
 * `GET /admin/ingestion/jobs/{id}`, so it must be kept separately from the
 * tracked job's status.
 */
export interface BulkUploadFileResult {
  filename: string;
  tableName: string | null;
  accepted: boolean;
  reason: string | null;
}

/** Result of one bulk synthetic CSV upload request. `jobId`/`status` are
 * `null` when zero files were accepted -- no job was created, so there is
 * nothing to track, only the per-file rejection reasons in `files`.
 */
export interface BulkUploadResult {
  jobId: number | null;
  status: string | null;
  files: BulkUploadFileResult[];
}
