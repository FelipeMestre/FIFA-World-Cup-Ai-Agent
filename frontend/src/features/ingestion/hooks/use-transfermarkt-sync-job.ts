"use client";

import { useCallback, useEffect, useState } from "react";

import { getJobStatus } from "@/features/ingestion/api/get-job-status";
import { triggerTransfermarktSync } from "@/features/ingestion/api/trigger-transfermarkt-sync";
import type { JobStatus } from "@/features/ingestion/types";
import { ApiError } from "@/lib/api/client";

const LAST_JOB_ID_STORAGE_KEY = "identity-links:last-transfermarkt-sync-job-id";

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

/** Tracks the most recently launched Transfermarkt sync job: trigger a new
 * run, and manually refresh its status/stage via the existing
 * `GET /admin/ingestion/jobs/{id}` endpoint. No automatic polling -- the
 * admin refreshes on demand.
 */
export function useTransfermarktSyncJob() {
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const trigger = useCallback(
    async (skipPopulated: boolean) => {
      setIsTriggering(true);
      setError(null);
      try {
        const result = await triggerTransfermarktSync(skipPopulated);
        writeLastJobId(result.jobId);
        // Triggers the `jobId` effect below to fetch full status -- avoids
        // a duplicate immediate fetch here.
        setJobId(result.jobId);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Couldn't launch the sync job");
      } finally {
        setIsTriggering(false);
      }
    },
    [],
  );

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
