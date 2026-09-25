import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getJobStatusMock = vi.fn();
vi.mock("@/features/ingestion/api/get-job-status", () => ({
  getJobStatus: (...args: unknown[]) => getJobStatusMock(...args),
}));

const uploadBulkSyntheticCsvsMock = vi.fn();
vi.mock("@/features/ingestion/api/upload-bulk-synthetic-csvs", () => ({
  uploadBulkSyntheticCsvs: (...args: unknown[]) => uploadBulkSyntheticCsvsMock(...args),
}));

const { useBulkSyntheticUploadJob } = await import(
  "@/features/ingestion/hooks/use-bulk-synthetic-upload-job"
);

function jobStatus(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    jobId: 9,
    jobType: "bulk_synthetic_upload" as const,
    status: "running" as const,
    rowCounts: {},
    errorMessage: null,
    currentStage: "team",
    stageCheckpoints: [{ stage: "team", completedAt: "2026-09-25T12:00:00Z" }],
    allStages: ["team", "player", "match"],
    ...overrides,
  };
}

function uploadResult(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    jobId: 9,
    status: "queued",
    files: [{ filename: "teams.csv", tableName: "team", accepted: true, reason: null }],
    ...overrides,
  };
}

const fakeFile = new File(["a,b\n1,2"], "teams.csv", { type: "text/csv" });

describe("useBulkSyntheticUploadJob", () => {
  beforeEach(() => {
    getJobStatusMock.mockReset();
    uploadBulkSyntheticCsvsMock.mockReset();
    window.localStorage.clear();
  });

  it("starts with no tracked job or upload result when localStorage is empty", () => {
    const { result } = renderHook(() => useBulkSyntheticUploadJob());

    expect(result.current.jobId).toBeNull();
    expect(result.current.job).toBeNull();
    expect(result.current.uploadResult).toBeNull();
    expect(getJobStatusMock).not.toHaveBeenCalled();
  });

  it("uploads files, tracks the returned job id, and fetches its status", async () => {
    uploadBulkSyntheticCsvsMock.mockResolvedValue(uploadResult());
    getJobStatusMock.mockResolvedValue(jobStatus());
    const { result } = renderHook(() => useBulkSyntheticUploadJob());

    await act(async () => {
      await result.current.upload([fakeFile]);
    });

    expect(uploadBulkSyntheticCsvsMock).toHaveBeenCalledWith([fakeFile]);
    await waitFor(() => expect(result.current.jobId).toBe(9));
    await waitFor(() => expect(result.current.job).not.toBeNull());
    expect(getJobStatusMock).toHaveBeenCalledWith(9);
    expect(
      window.localStorage.getItem("ingestion:last-bulk-synthetic-upload-job-id"),
    ).toBe("9");
  });

  it("keeps the per-file upload result even after the job status is refreshed", async () => {
    uploadBulkSyntheticCsvsMock.mockResolvedValue(uploadResult());
    getJobStatusMock.mockResolvedValue(jobStatus());
    const { result } = renderHook(() => useBulkSyntheticUploadJob());

    await act(async () => {
      await result.current.upload([fakeFile]);
    });
    await waitFor(() => expect(result.current.job).not.toBeNull());

    getJobStatusMock.mockResolvedValueOnce(jobStatus({ status: "succeeded" }));
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.uploadResult).toEqual(uploadResult());
    expect(result.current.job?.status).toBe("succeeded");
  });

  it("does not track a job when zero files were accepted", async () => {
    uploadBulkSyntheticCsvsMock.mockResolvedValue({
      jobId: null,
      status: null,
      files: [
        { filename: "unknown.csv", tableName: null, accepted: false, reason: "unrecognized filename" },
      ],
    });
    const { result } = renderHook(() => useBulkSyntheticUploadJob());

    await act(async () => {
      await result.current.upload([fakeFile]);
    });

    expect(result.current.jobId).toBeNull();
    expect(result.current.uploadResult?.files).toHaveLength(1);
    expect(getJobStatusMock).not.toHaveBeenCalled();
    expect(
      window.localStorage.getItem("ingestion:last-bulk-synthetic-upload-job-id"),
    ).toBeNull();
  });

  it("restores a previously tracked job id from localStorage on mount", async () => {
    window.localStorage.setItem("ingestion:last-bulk-synthetic-upload-job-id", "5");
    getJobStatusMock.mockResolvedValue(jobStatus({ jobId: 5 }));

    const { result } = renderHook(() => useBulkSyntheticUploadJob());

    await waitFor(() => expect(result.current.jobId).toBe(5));
    expect(getJobStatusMock).toHaveBeenCalledWith(5);
  });

  it("surfaces an upload error without crashing", async () => {
    uploadBulkSyntheticCsvsMock.mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useBulkSyntheticUploadJob());

    await act(async () => {
      await result.current.upload([fakeFile]);
    });

    expect(result.current.error).toBe("Couldn't upload the files");
    expect(result.current.jobId).toBeNull();
  });

  it("surfaces a refresh error without crashing", async () => {
    window.localStorage.setItem("ingestion:last-bulk-synthetic-upload-job-id", "9");
    getJobStatusMock.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useBulkSyntheticUploadJob());

    await waitFor(() => expect(result.current.error).toBe("Couldn't load job status"));
    expect(result.current.job).toBeNull();
  });
});
