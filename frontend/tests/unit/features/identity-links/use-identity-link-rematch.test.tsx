import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getJobStatusMock = vi.fn();
vi.mock("@/features/ingestion/api/get-job-status", () => ({
  getJobStatus: (...args: unknown[]) => getJobStatusMock(...args),
}));

const triggerIdentityLinkRematchMock = vi.fn();
vi.mock("@/features/identity-links/api/trigger-identity-link-rematch", () => ({
  triggerIdentityLinkRematch: (...args: unknown[]) => triggerIdentityLinkRematchMock(...args),
}));

const { useIdentityLinkRematch } = await import(
  "@/features/identity-links/hooks/use-identity-link-rematch"
);

function jobStatus(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    jobId: 9,
    jobType: "identity_link_rematch" as const,
    status: "running" as const,
    rowCounts: {},
    errorMessage: null,
    currentStage: null,
    stageCheckpoints: [],
    allStages: [],
    ...overrides,
  };
}

describe("useIdentityLinkRematch", () => {
  beforeEach(() => {
    getJobStatusMock.mockReset();
    triggerIdentityLinkRematchMock.mockReset();
    window.localStorage.clear();
  });

  it("starts with no tracked job when localStorage is empty", async () => {
    const { result } = renderHook(() => useIdentityLinkRematch());

    expect(result.current.jobId).toBeNull();
    expect(result.current.job).toBeNull();
    expect(getJobStatusMock).not.toHaveBeenCalled();
  });

  it("triggers a rematch, tracks the returned job id, and fetches its status", async () => {
    triggerIdentityLinkRematchMock.mockResolvedValue({ jobId: 9, status: "queued" });
    getJobStatusMock.mockResolvedValue(jobStatus());
    const { result } = renderHook(() => useIdentityLinkRematch());

    await act(async () => {
      await result.current.trigger();
    });

    expect(triggerIdentityLinkRematchMock).toHaveBeenCalledWith();
    await waitFor(() => expect(result.current.jobId).toBe(9));
    await waitFor(() => expect(result.current.job).not.toBeNull());
    expect(getJobStatusMock).toHaveBeenCalledWith(9);
    expect(window.localStorage.getItem("identity-links:last-rematch-job-id")).toBe("9");
  });

  it("restores a previously tracked job id from localStorage on mount", async () => {
    window.localStorage.setItem("identity-links:last-rematch-job-id", "3");
    getJobStatusMock.mockResolvedValue(jobStatus({ jobId: 3 }));

    const { result } = renderHook(() => useIdentityLinkRematch());

    await waitFor(() => expect(result.current.jobId).toBe(3));
    expect(getJobStatusMock).toHaveBeenCalledWith(3);
  });

  it("re-fetches the tracked job's status when refresh is called", async () => {
    window.localStorage.setItem("identity-links:last-rematch-job-id", "9");
    getJobStatusMock.mockResolvedValueOnce(jobStatus({ status: "running" }));
    const { result } = renderHook(() => useIdentityLinkRematch());
    await waitFor(() => expect(result.current.job?.status).toBe("running"));

    getJobStatusMock.mockResolvedValueOnce(jobStatus({ status: "succeeded" }));
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.job?.status).toBe("succeeded");
    expect(getJobStatusMock).toHaveBeenCalledTimes(2);
  });

  it("surfaces a trigger error without crashing", async () => {
    triggerIdentityLinkRematchMock.mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useIdentityLinkRematch());

    await act(async () => {
      await result.current.trigger();
    });

    expect(result.current.error).toBe("Couldn't launch the rematch job");
    expect(result.current.jobId).toBeNull();
  });

  it("surfaces a refresh error without crashing", async () => {
    window.localStorage.setItem("identity-links:last-rematch-job-id", "9");
    getJobStatusMock.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useIdentityLinkRematch());

    await waitFor(() => expect(result.current.error).toBe("Couldn't load job status"));
    expect(result.current.job).toBeNull();
  });

  it("calls onRematchSucceeded exactly once when the tracked job's status becomes succeeded", async () => {
    triggerIdentityLinkRematchMock.mockResolvedValue({ jobId: 9, status: "queued" });
    getJobStatusMock.mockResolvedValueOnce(jobStatus({ status: "running" }));
    const onRematchSucceeded = vi.fn();
    const { result } = renderHook(() => useIdentityLinkRematch(onRematchSucceeded));

    await act(async () => {
      await result.current.trigger();
    });
    await waitFor(() => expect(result.current.job?.status).toBe("running"));
    expect(onRematchSucceeded).not.toHaveBeenCalled();

    getJobStatusMock.mockResolvedValueOnce(jobStatus({ status: "succeeded" }));
    await act(async () => {
      await result.current.refresh();
    });
    await waitFor(() => expect(result.current.job?.status).toBe("succeeded"));
    expect(onRematchSucceeded).toHaveBeenCalledTimes(1);

    // A subsequent manual refresh landing on the same already-succeeded job
    // must not notify again.
    getJobStatusMock.mockResolvedValueOnce(jobStatus({ status: "succeeded" }));
    await act(async () => {
      await result.current.refresh();
    });
    expect(onRematchSucceeded).toHaveBeenCalledTimes(1);
  });

  it("does not call onRematchSucceeded while the job is only queued or running", async () => {
    window.localStorage.setItem("identity-links:last-rematch-job-id", "9");
    getJobStatusMock.mockResolvedValue(jobStatus({ status: "running" }));
    const onRematchSucceeded = vi.fn();

    renderHook(() => useIdentityLinkRematch(onRematchSucceeded));

    await waitFor(() => expect(getJobStatusMock).toHaveBeenCalled());
    expect(onRematchSucceeded).not.toHaveBeenCalled();
  });
});
