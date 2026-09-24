export type IngestionJobType = "synthetic_upload" | "transfermarkt_sync";

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
