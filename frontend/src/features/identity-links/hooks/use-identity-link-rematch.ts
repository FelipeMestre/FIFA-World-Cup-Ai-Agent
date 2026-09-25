"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { triggerIdentityLinkRematch } from "@/features/identity-links/api/trigger-identity-link-rematch";
import { getJobStatus } from "@/features/ingestion/api/get-job-status";
import type { JobStatus } from "@/features/ingestion/types";
import { ApiError } from "@/lib/api/client";

const LAST_JOB_ID_STORAGE_KEY = "identity-links:last-rematch-job-id";

function readLastJobId(): number | null {
  try {
    const stored = window.localStorage.getItem(LAST_JOB_ID_STORAGE_KEY);
    return stored ? Number(stored) : null;
  } catch {
    return null;
  }
}

function writeLastJobId(jobId: number): void {
  try {
    window.localStorage.setItem(LAST_JOB_ID_STORAGE_KEY, String(jobId));
  } catch {
    // Per-viewer convenience only -- a blocked/private-mode localStorage
    // just means the job id won't survive a reload, nothing more.
  }
}

/** Tracks the most recently launched identity-link clean-rematch job:
 * trigger a new wipe+regenerate run, and manually refresh its status via
 * the existing generic `GET /admin/ingestion/jobs/{id}` endpoint (reused via
 * `getJobStatus`, which already parses any `IngestionJobType`). Mirrors
 * `useTransfermarktSyncJob`'s manual-refresh-only pattern -- no polling.
 *
 * A rematch wipes and regenerates every `player_identity_link` row, so a
 * caller showing a list of those rows needs to know when to refetch it.
 * `onRematchSucceeded` fires once per job the first time its status is
 * observed as `succeeded` (whether that's from the post-trigger fetch or a
 * manual refresh click), so the caller can pass its own list-refresh
 * function straight in instead of polling `job.status` itself.
 */
export function useIdentityLinkRematch(onRematchSucceeded?: () => void) {
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notifiedJobIdRef = useRef<number | null>(null);

  useEffect(() => {
    const lastJobId = readLastJobId();
    if (lastJobId !== null) {
      setJobId(lastJobId);
    }
  }, []);

  const refresh = useCallback(async (targetJobId: number) => {
    setIsRefreshing(true);
    setError(null);
    try {
      const status = await getJobStatus(targetJobId);
      setJob(status);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Couldn't load job status");
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (jobId !== null) {
      void refresh(jobId);
    }
  }, [jobId, refresh]);

  useEffect(() => {
    if (job?.status === "succeeded" && notifiedJobIdRef.current !== job.jobId) {
      notifiedJobIdRef.current = job.jobId;
      onRematchSucceeded?.();
    }
  }, [job, onRematchSucceeded]);

  const trigger = useCallback(async () => {
    setIsTriggering(true);
    setError(null);
    try {
      const result = await triggerIdentityLinkRematch();
      writeLastJobId(result.jobId);
      // Triggers the `jobId` effect above to fetch full status -- avoids a
      // duplicate immediate fetch here.
      setJobId(result.jobId);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Couldn't launch the rematch job");
    } finally {
      setIsTriggering(false);
    }
  }, []);

  return {
    jobId,
    job,
    isTriggering,
    isRefreshing,
    error,
    trigger,
    refresh: useCallback(() => {
      if (jobId !== null) return refresh(jobId);
      return Promise.resolve();
    }, [jobId, refresh]),
  };
}
