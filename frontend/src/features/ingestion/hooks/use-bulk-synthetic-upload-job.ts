"use client";

import { useCallback, useEffect, useState } from "react";

import { getJobStatus } from "@/features/ingestion/api/get-job-status";
import { uploadBulkSyntheticCsvs } from "@/features/ingestion/api/upload-bulk-synthetic-csvs";
import type { BulkUploadResult, JobStatus } from "@/features/ingestion/types";
import { ApiError } from "@/lib/api/client";

const LAST_JOB_ID_STORAGE_KEY = "ingestion:last-bulk-synthetic-upload-job-id";

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

/** Tracks the most recently launched bulk synthetic CSV upload. Mirrors
 * `useTransfermarktSyncJob` exactly for the job-tracking half: trigger once,
 * fetch status once when a job id appears, fetch once on mount if a job id
 * is cached in `localStorage`, and otherwise only refetch on a manual
 * "Refresh" call -- no polling loop, no terminal-status stop condition.
 *
 * The one addition beyond that mirror is `uploadResult`: the per-file
 * accept/reject breakdown from the upload response itself. That breakdown
 * has no equivalent in `GET /admin/ingestion/jobs/{id}`, so it is kept in
 * its own piece of state instead of being folded into (and lost when)
 * `job` is next refreshed.
 */
export function useBulkSyntheticUploadJob() {
  const [jobId, setJobId] = useState<number | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [uploadResult, setUploadResult] = useState<BulkUploadResult | null>(null);
  const [isUploading, setIsUploading] = useState(false);
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

  const upload = useCallback(async (files: File[]) => {
    setIsUploading(true);
    setError(null);
    try {
      const result = await uploadBulkSyntheticCsvs(files);
      setUploadResult(result);
      if (result.jobId !== null) {
        writeLastJobId(result.jobId);
        // Triggers the `jobId` effect above to fetch full status -- avoids
        // a duplicate immediate fetch here.
        setJobId(result.jobId);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Couldn't upload the files");
    } finally {
      setIsUploading(false);
    }
  }, []);

  return {
    jobId,
    job,
    uploadResult,
    isUploading,
    isRefreshing,
    error,
    upload,
    refresh: useCallback(() => {
      if (jobId !== null) return refresh(jobId);
      return Promise.resolve();
    }, [jobId, refresh]),
  };
}
