import { z } from "zod";

import type { IngestionJobStatus, IngestionJobType, JobStatus } from "@/features/ingestion/types";

const jobTypeSchema = z.enum(["synthetic_upload", "transfermarkt_sync", "identity_link_rematch"]);
const jobStatusValueSchema = z.enum(["queued", "running", "succeeded", "failed"]);

const stageCheckpointSchema = z.object({
  stage: z.string(),
  completed_at: z.string(),
});

export const jobStatusSchema = z.object({
  job_id: z.number().int(),
  job_type: jobTypeSchema,
  status: jobStatusValueSchema,
  row_counts: z.record(z.string(), z.number().int()),
  error_message: z.string().nullable(),
  current_stage: z.string().nullable(),
  stage_checkpoints: z.array(stageCheckpointSchema),
  all_stages: z.array(z.string()),
});

export function toJobStatus(row: z.infer<typeof jobStatusSchema>): JobStatus {
  return {
    jobId: row.job_id,
    jobType: row.job_type as IngestionJobType,
    status: row.status as IngestionJobStatus,
    rowCounts: row.row_counts,
    errorMessage: row.error_message,
    currentStage: row.current_stage,
    stageCheckpoints: row.stage_checkpoints.map((checkpoint) => ({
      stage: checkpoint.stage,
      completedAt: checkpoint.completed_at,
    })),
    allStages: row.all_stages,
  };
}
