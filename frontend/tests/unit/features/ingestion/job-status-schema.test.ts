import { describe, expect, it } from "vitest";

import { jobStatusSchema, toJobStatus } from "@/features/ingestion/schemas/job-status.schema";

function baseWireRow() {
  return {
    job_id: 4,
    job_type: "transfermarkt_sync" as const,
    status: "running" as const,
    row_counts: {},
    error_message: null,
    current_stage: "player_valuations",
    stage_checkpoints: [
      { stage: "national_teams", completed_at: "2026-09-24T19:00:00+00:00" },
      { stage: "clubs", completed_at: "2026-09-24T19:00:01+00:00" },
    ],
    all_stages: ["national_teams", "clubs", "players"],
  };
}

describe("jobStatusSchema / toJobStatus", () => {
  it("maps snake_case wire fields to the camelCase domain shape", () => {
    const row = jobStatusSchema.parse(baseWireRow());

    const status = toJobStatus(row);

    expect(status).toMatchObject({
      jobId: 4,
      jobType: "transfermarkt_sync",
      status: "running",
      currentStage: "player_valuations",
      allStages: ["national_teams", "clubs", "players"],
    });
    expect(status.stageCheckpoints).toEqual([
      { stage: "national_teams", completedAt: "2026-09-24T19:00:00+00:00" },
      { stage: "clubs", completedAt: "2026-09-24T19:00:01+00:00" },
    ]);
  });

  it("keeps a queued job's null stage and empty checkpoints as-is", () => {
    const row = jobStatusSchema.parse({
      ...baseWireRow(),
      status: "queued",
      current_stage: null,
      stage_checkpoints: [],
    });

    const status = toJobStatus(row);

    expect(status.currentStage).toBeNull();
    expect(status.stageCheckpoints).toEqual([]);
  });

  it("keeps a synthetic_upload job's empty all_stages, not a Transfermarkt stage list", () => {
    const row = jobStatusSchema.parse({
      ...baseWireRow(),
      job_type: "synthetic_upload",
      current_stage: null,
      stage_checkpoints: [],
      all_stages: [],
    });

    expect(toJobStatus(row).allStages).toEqual([]);
  });
});
