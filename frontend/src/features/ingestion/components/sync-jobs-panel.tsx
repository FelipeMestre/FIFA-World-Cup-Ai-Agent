"use client";

import { useId, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { StageProgress } from "@/features/ingestion/components/stage-progress";
import { useTransfermarktSyncJob } from "@/features/ingestion/hooks/use-transfermarkt-sync-job";
import type { IngestionJobStatus } from "@/features/ingestion/types";

const STATUS_BADGE_VARIANT: Record<IngestionJobStatus, "outline" | "default" | "destructive"> = {
  queued: "outline",
  running: "default",
  succeeded: "default",
  failed: "destructive",
};

/** Admin panel to launch a Transfermarkt sync job and check its progress.
 * Polling is manual: a "Refresh" button re-hits the existing
 * `GET /admin/ingestion/jobs/{id}` endpoint rather than the panel polling
 * on an interval.
 */
export function SyncJobsPanel() {
  const { jobId, job, isTriggering, isRefreshing, error, trigger, refresh } =
    useTransfermarktSyncJob();
  const [skipPopulated, setSkipPopulated] = useState(false);
  const skipPopulatedId = useId();

  return (
    <div className="flex flex-col gap-ds-4">
      <div>
        <h1 className="text-heading-lg">Transfermarkt sync jobs</h1>
        <p className="text-body-sm text-ink-secondary">
          Launch a roster-scoped Transfermarkt sync and track which stage it&apos;s on.
        </p>
      </div>

      <Card className="border border-border-subtle bg-surface-800 text-ink-primary">
        <CardHeader className="flex flex-row items-center justify-between gap-ds-3 border-b border-border-subtle pb-ds-3">
          <span className="text-label-sm text-ink-muted">Launch a new sync</span>
        </CardHeader>
        <CardContent className="flex flex-col gap-ds-3 pt-ds-4">
          <label htmlFor={skipPopulatedId} className="flex items-center gap-ds-2 text-body-sm text-ink-secondary">
            <input
              id={skipPopulatedId}
              type="checkbox"
              checked={skipPopulated}
              onChange={(event) => setSkipPopulated(event.target.checked)}
              className="size-4 rounded border-border-strong accent-accent-live"
            />
            Resume mode -- skip a step whose target table already has rows
          </label>
        </CardContent>
        <CardFooter className="justify-end gap-ds-2 border-border-subtle bg-surface-800">
          <Button
            type="button"
            disabled={isTriggering}
            onClick={() => void trigger(skipPopulated)}
            className="bg-brand text-on-brand hover:bg-brand-strong"
          >
            {isTriggering ? "Launching…" : "Launch sync"}
          </Button>
        </CardFooter>
      </Card>

      {error ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-4 text-body-sm text-data-negative">
          {error}
        </p>
      ) : null}

      {jobId === null ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-6 text-center text-body-md text-ink-secondary">
          No sync job launched yet.
        </p>
      ) : (
        <Card className="border border-border-subtle bg-surface-800 text-ink-primary">
          <CardHeader className="flex flex-row items-center justify-between gap-ds-3 border-b border-border-subtle pb-ds-3">
            <div className="flex items-center gap-ds-2">
              <span className="text-label-sm text-ink-muted">Job #{jobId}</span>
              {job ? (
                <Badge variant={STATUS_BADGE_VARIANT[job.status]}>{job.status}</Badge>
              ) : null}
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
