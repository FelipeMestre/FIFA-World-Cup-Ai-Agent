import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getJobStatusMock = vi.fn();
vi.mock("@/features/ingestion/api/get-job-status", () => ({
  getJobStatus: (...args: unknown[]) => getJobStatusMock(...args),
}));

const triggerTransfermarktSyncMock = vi.fn();
vi.mock("@/features/ingestion/api/trigger-transfermarkt-sync", () => ({
  triggerTransfermarktSync: (...args: unknown[]) => triggerTransfermarktSyncMock(...args),
}));

const { useTransfermarktSyncJob } = await import(
  "@/features/ingestion/hooks/use-transfermarkt-sync-job"
);

function jobStatus(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    jobId: 4,
    jobType: "transfermarkt_sync" as const,
    status: "running" as const,
    rowCounts: {},
    errorMessage: null,
    currentStage: "clubs",
    stageCheckpoints: [{ stage: "clubs", completedAt: "2026-09-24T19:00:00Z" }],
    allStages: ["national_teams", "clubs", "players"],
    ...overrides,
  };
}

describe("useTransfermarktSyncJob", () => {
  beforeEach(() => {
    getJobStatusMock.mockReset();
    triggerTransfermarktSyncMock.mockReset();
    window.localStorage.clear();
  });

  it("starts with no tracked job when localStorage is empty", async () => {
    const { result } = renderHook(() => useTransfermarktSyncJob());

    expect(result.current.jobId).toBeNull();
    expect(result.current.job).toBeNull();
    expect(getJobStatusMock).not.toHaveBeenCalled();
  });

  it("triggers a sync, tracks the returned job id, and fetches its status", async () => {
    triggerTransfermarktSyncMock.mockResolvedValue({ jobId: 4, status: "queued" });
    getJobStatusMock.mockResolvedValue(jobStatus());
    const { result } = renderHook(() => useTransfermarktSyncJob());

    await act(async () => {
      await result.current.trigger(false);
    });

    expect(triggerTransfermarktSyncMock).toHaveBeenCalledWith(false);
    await waitFor(() => expect(result.current.jobId).toBe(4));
    await waitFor(() => expect(result.current.job).not.toBeNull());
    expect(getJobStatusMock).toHaveBeenCalledWith(4);
    expect(window.localStorage.getItem("identity-links:last-transfermarkt-sync-job-id")).toBe(
      "4",
    );
  });

  it("restores a previously tracked job id from localStorage on mount", async () => {
    window.localStorage.setItem("identity-links:last-transfermarkt-sync-job-id", "7");
    getJobStatusMock.mockResolvedValue(jobStatus({ jobId: 7 }));

    const { result } = renderHook(() => useTransfermarktSyncJob());

    await waitFor(() => expect(result.current.jobId).toBe(7));
    expect(getJobStatusMock).toHaveBeenCalledWith(7);
  });

  it("re-fetches the tracked job's status when refresh is called", async () => {
    window.localStorage.setItem("identity-links:last-transfermarkt-sync-job-id", "4");
    getJobStatusMock.mockResolvedValueOnce(jobStatus({ status: "running" }));
    const { result } = renderHook(() => useTransfermarktSyncJob());
    await waitFor(() => expect(result.current.job?.status).toBe("running"));

    getJobStatusMock.mockResolvedValueOnce(jobStatus({ status: "succeeded" }));
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.job?.status).toBe("succeeded");
    expect(getJobStatusMock).toHaveBeenCalledTimes(2);
  });

  it("surfaces a trigger error without crashing", async () => {
    triggerTransfermarktSyncMock.mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useTransfermarktSyncJob());

    await act(async () => {
      await result.current.trigger(false);
    });

    expect(result.current.error).toBe("Couldn't launch the sync job");
    expect(result.current.jobId).toBeNull();
  });

  it("surfaces a refresh error without crashing", async () => {
    window.localStorage.setItem("identity-links:last-transfermarkt-sync-job-id", "4");
    getJobStatusMock.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useTransfermarktSyncJob());

    await waitFor(() => expect(result.current.error).toBe("Couldn't load job status"));
    expect(result.current.job).toBeNull();
  });
});
