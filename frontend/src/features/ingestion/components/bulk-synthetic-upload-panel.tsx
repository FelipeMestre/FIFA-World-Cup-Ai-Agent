"use client";

import { useId, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { StageProgress } from "@/features/ingestion/components/stage-progress";
import { useBulkSyntheticUploadJob } from "@/features/ingestion/hooks/use-bulk-synthetic-upload-job";
import type { IngestionJobStatus } from "@/features/ingestion/types";

const STATUS_BADGE_VARIANT: Record<IngestionJobStatus, "outline" | "default" | "destructive"> = {
  queued: "outline",
  running: "default",
  succeeded: "default",
  failed: "destructive",
};

/** Admin panel to upload a batch of synthetic dataset CSVs in one request and
 * track the resulting ingestion job's progress. Mirrors `SyncJobsPanel`'s job
 * status card exactly (same manual-refresh-only pattern, same `StageProgress`
 * rendering), plus the per-file accept/reject breakdown that only exists in
 * the upload response itself and is shown regardless of whether any file was
 * accepted.
 */
export function BulkSyntheticUploadPanel() {
  const { jobId, job, uploadResult, isUploading, isRefreshing, error, upload, refresh } =
    useBulkSyntheticUploadJob();
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const filesInputId = useId();

  function handleSubmit() {
    if (selectedFiles.length === 0) return;
    void upload(selectedFiles);
  }

  const acceptedCount = uploadResult?.files.filter((file) => file.accepted).length ?? 0;

  return (
    <div className="flex flex-col gap-ds-4">
      <div>
        <h2 className="text-heading-md">Bulk synthetic CSV upload</h2>
        <p className="text-body-sm text-ink-secondary">
          Upload multiple synthetic dataset CSVs at once -- each file&apos;s target table is
          resolved from its filename and every accepted file is ingested as one FK-safe
          ordered job.
        </p>
      </div>

      <Card className="border border-border-subtle bg-surface-800 text-ink-primary">
        <CardHeader className="flex flex-row items-center justify-between gap-ds-3 border-b border-border-subtle pb-ds-3">
          <span className="text-label-sm text-ink-muted">Upload CSVs</span>
        </CardHeader>
        <CardContent className="flex flex-col gap-ds-3 pt-ds-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={filesInputId} className="text-label-md text-ink-secondary">
              Synthetic dataset CSVs
            </Label>
            <input
              id={filesInputId}
              type="file"
              multiple
              accept=".csv"
              onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))}
              className="text-body-sm text-ink-secondary file:mr-ds-3 file:rounded-md file:border file:border-border-strong file:bg-surface-900 file:px-ds-3 file:py-ds-2 file:text-ink-primary"
            />
            {selectedFiles.length > 0 ? (
              <p className="text-label-sm text-ink-muted">
                {selectedFiles.length} file{selectedFiles.length === 1 ? "" : "s"} selected
              </p>
            ) : null}
          </div>
        </CardContent>
        <CardFooter className="justify-end gap-ds-2 border-border-subtle bg-surface-800">
          <Button
            type="button"
            disabled={isUploading || selectedFiles.length === 0}
            onClick={handleSubmit}
            className="bg-brand text-on-brand hover:bg-brand-strong"
          >
            {isUploading ? "Uploading…" : "Upload files"}
          </Button>
        </CardFooter>
      </Card>

      {error ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-4 text-body-sm text-data-negative">
          {error}
        </p>
      ) : null}

      {uploadResult ? (
        <Card className="border border-border-subtle bg-surface-800 text-ink-primary">
          <CardHeader className="flex flex-row items-center justify-between gap-ds-3 border-b border-border-subtle pb-ds-3">
            <span className="text-label-sm text-ink-muted">
              Upload results -- {acceptedCount} of {uploadResult.files.length} accepted
            </span>
          </CardHeader>
          <CardContent className="flex flex-col gap-ds-2 pt-ds-4">
            <ul className="flex flex-col gap-ds-2">
              {uploadResult.files.map((file) => (
                <li
                  key={file.filename}
                  className="flex flex-col gap-1 rounded-lg border border-border-subtle p-ds-3 text-body-sm sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex items-center gap-ds-2">
                    <Badge variant={file.accepted ? "default" : "destructive"}>
                      {file.accepted ? "Accepted" : "Rejected"}
                    </Badge>
                    <span className="text-ink-primary">{file.filename}</span>
                  </div>
                  <span className="text-ink-secondary">
                    {file.accepted ? `-> ${file.tableName}` : file.reason}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {jobId === null ? null : (
        <Card className="border border-border-subtle bg-surface-800 text-ink-primary">
          <CardHeader className="flex flex-row items-center justify-between gap-ds-3 border-b border-border-subtle pb-ds-3">
            <div className="flex items-center gap-ds-2">
              <span className="text-label-sm text-ink-muted">Job #{jobId}</span>
              {job ? <Badge variant={STATUS_BADGE_VARIANT[job.status]}>{job.status}</Badge> : null}
            </div>
            <Button
              type="button"
              variant="outline"
              disabled={isRefreshing}
              onClick={() => void refresh()}
              className="border-border-strong text-ink-primary hover:bg-surface-700"
            >
              {isRefreshing ? "Refreshing…" : "Refresh"}
            </Button>
          </CardHeader>
          <CardContent className="flex flex-col gap-ds-4 pt-ds-4">
            {job ? (
              <>
                <StageProgress job={job} />
                {job.errorMessage ? (
                  <p className="text-body-sm text-data-negative">{job.errorMessage}</p>
                ) : null}
                {Object.keys(job.rowCounts).length > 0 ? (
                  <dl className="grid grid-cols-2 gap-x-ds-3 gap-y-1 text-body-sm text-ink-secondary sm:grid-cols-3">
                    {Object.entries(job.rowCounts).map(([table, count]) => (
                      <div key={table} className="flex justify-between gap-ds-2">
                        <dt className="text-ink-muted">{table}</dt>
                        <dd>{count}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
              </>
            ) : (
              <p className="text-body-sm text-ink-secondary">Loading job status…</p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
