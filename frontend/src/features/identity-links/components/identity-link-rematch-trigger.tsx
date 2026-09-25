"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { IngestionJobStatus, JobStatus } from "@/features/ingestion/types";

const STATUS_BADGE_VARIANT: Record<IngestionJobStatus, "outline" | "default" | "destructive"> = {
  queued: "outline",
  running: "default",
  succeeded: "default",
  failed: "destructive",
};

/** Destructive-operation trigger for `POST /admin/identity-links/rematch`:
 * wipes every `player_identity_link` row (including manually reviewed ones)
 * and regenerates them from the current rosters. Requires an explicit
 * confirmation dialog before firing -- a single unconfirmed click must not
 * be able to delete admin review history.
 */
export function IdentityLinkRematchTrigger({
  jobId,
  job,
  isTriggering,
  isRefreshing,
  error,
  trigger,
  refresh,
}: {
  jobId: number | null;
  job: JobStatus | null;
  isTriggering: boolean;
  isRefreshing: boolean;
  error: string | null;
  trigger: () => Promise<void>;
  refresh: () => Promise<void>;
}) {
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function handleConfirm() {
    await trigger();
    setConfirmOpen(false);
  }

  return (
    <Card className="border border-border-subtle bg-surface-800 text-ink-primary">
      <CardHeader className="flex flex-row items-center justify-between gap-ds-3 border-b border-border-subtle pb-ds-3">
        <div>
          <span className="text-label-sm text-ink-muted">Clean rematch</span>
          <p className="text-body-sm text-ink-secondary">
            Wipes every identity link and regenerates them from the current rosters.
          </p>
        </div>
        <Button
          type="button"
          disabled={isTriggering}
          onClick={() => setConfirmOpen(true)}
          className="bg-brand text-on-brand hover:bg-brand-strong"
        >
          {isTriggering ? "Launching…" : "Rematch identity links"}
        </Button>
      </CardHeader>

      {error ? (
        <CardContent className="pt-ds-4">
          <p className="text-body-sm text-data-negative">{error}</p>
        </CardContent>
      ) : null}

      {jobId !== null ? (
        <CardContent className="flex flex-col gap-ds-3 pt-ds-4">
          <div className="flex items-center justify-between gap-ds-3">
            <div className="flex items-center gap-ds-2">
              <span className="text-label-sm text-ink-muted">Job #{jobId}</span>
              {job ? (
                <Badge variant={STATUS_BADGE_VARIANT[job.status]}>{job.status}</Badge>
              ) : null}
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isRefreshing}
              onClick={() => void refresh()}
              className="border-border-strong text-ink-primary hover:bg-surface-700"
            >
              {isRefreshing ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
          {job === null ? (
            <p className="text-body-sm text-ink-secondary">Loading job status…</p>
          ) : (
            <>
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
          )}
        </CardContent>
      ) : null}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="bg-surface-800 text-ink-primary ring-border-strong">
          <DialogHeader>
            <DialogTitle>Rematch every identity link?</DialogTitle>
            <DialogDescription className="text-ink-secondary">
              This deletes every current identity link -- including links already approved,
              rejected, or manually reassigned -- and regenerates all of them from scratch
              against the current rosters. Deleted admin review history cannot be recovered.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="border-border-subtle bg-surface-800">
            <Button type="button" variant="outline" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={isTriggering}
              onClick={() => void handleConfirm()}
              className="bg-brand text-on-brand hover:bg-brand-strong"
            >
              {isTriggering ? "Rematching…" : "Yes, wipe and regenerate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
