"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { CorrectMatchDialog } from "@/features/identity-links/components/correct-match-dialog";
import type { IdentityLinkReview, MatchMethod } from "@/features/identity-links/types";
import { ApiError } from "@/lib/api/client";

const MATCH_METHOD_LABEL: Record<MatchMethod, string> = {
  exact_name_dob: "Exact name + DOB",
  exact_name_team: "Exact name + team",
  fuzzy_name: "Fuzzy name match",
  manual: "Manually corrected",
};

function formatEur(value: number | null): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatConfidence(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

type Action = "approve" | "reject" | null;

/** One doubtful `player_identity_link` match, showing every comparison
 * field for both sides so the admin can decide without leaving this card.
 */
export function IdentityLinkReviewCard({
  review,
  onApprove,
  onReject,
  onReassign,
}: {
  review: IdentityLinkReview;
  onApprove: (linkId: number) => Promise<void>;
  onReject: (linkId: number) => Promise<void>;
  onReassign: (linkId: number, realPlayerId: number) => Promise<void>;
}) {
  const [pendingAction, setPendingAction] = useState<Action>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isCorrectMatchOpen, setIsCorrectMatchOpen] = useState(false);
  const { syntheticPlayer, realPlayer } = review;
  const isBusy = pendingAction !== null;

  async function runAction(action: Exclude<Action, null>, run: () => Promise<void>) {
    setPendingAction(action);
    setActionError(null);
    try {
      await run();
    } catch (caught) {
      setActionError(
        caught instanceof ApiError
          ? caught.message
          : `Couldn't ${action === "approve" ? "approve" : "reject"} this match`,
      );
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <Card className="border border-border-subtle bg-surface-800 text-ink-primary">
      <CardHeader className="flex flex-row items-center justify-between gap-ds-3 border-b border-border-subtle pb-ds-3">
        <div className="flex items-center gap-ds-2">
          <Badge variant="outline" className="border-border-strong text-ink-secondary">
            {MATCH_METHOD_LABEL[review.matchMethod]}
          </Badge>
          <span className="text-label-sm text-ink-muted">
            Confidence {formatConfidence(review.matchConfidence)}
          </span>
        </div>
        <span className="text-label-sm text-ink-muted">Link #{review.id}</span>
      </CardHeader>

      <CardContent className="grid gap-ds-4 pt-ds-4 md:grid-cols-2">
        <div className="flex flex-col gap-ds-2 rounded-lg border border-border-subtle bg-surface-900 p-ds-3">
          <span className="text-label-sm text-ink-muted">WC2026 roster</span>
          <span className="text-heading-sm">{syntheticPlayer.name}</span>
          <dl className="grid grid-cols-2 gap-x-ds-3 gap-y-1 text-body-sm text-ink-secondary">
            <dt className="text-ink-muted">Position</dt>
            <dd>{syntheticPlayer.position}</dd>
            <dt className="text-ink-muted">Club</dt>
            <dd>{syntheticPlayer.clubTeam}</dd>
            <dt className="text-ink-muted">Date of birth</dt>
            <dd>{syntheticPlayer.dateOfBirth}</dd>
            <dt className="text-ink-muted">Height</dt>
            <dd>{syntheticPlayer.heightCm} cm</dd>
            <dt className="text-ink-muted">Caps / Goals</dt>
            <dd>
              {syntheticPlayer.caps} / {syntheticPlayer.goals}
            </dd>
            <dt className="text-ink-muted">Market value</dt>
            <dd>{formatEur(syntheticPlayer.marketValueEur)}</dd>
          </dl>
        </div>

        <div className="flex flex-col gap-ds-2 rounded-lg border border-border-subtle bg-surface-900 p-ds-3">
          <span className="text-label-sm text-ink-muted">Transfermarkt</span>
          <span className="text-heading-sm">
            {realPlayer.firstName} {realPlayer.lastName}
          </span>
          <dl className="grid grid-cols-2 gap-x-ds-3 gap-y-1 text-body-sm text-ink-secondary">
            <dt className="text-ink-muted">Position</dt>
            <dd>
              {realPlayer.position}
              {realPlayer.subPosition ? ` (${realPlayer.subPosition})` : ""}
            </dd>
            <dt className="text-ink-muted">Nationality</dt>
            <dd>{realPlayer.countryOfCitizenship ?? "—"}</dd>
            <dt className="text-ink-muted">Date of birth</dt>
            <dd>{realPlayer.dateOfBirth ?? "—"}</dd>
            <dt className="text-ink-muted">Height</dt>
            <dd>{realPlayer.heightCm ? `${realPlayer.heightCm} cm` : "—"}</dd>
            <dt className="text-ink-muted">Caps / Goals</dt>
            <dd>
              {realPlayer.internationalCaps ?? "—"} / {realPlayer.internationalGoals ?? "—"}
            </dd>
            <dt className="text-ink-muted">Market value</dt>
            <dd>{formatEur(realPlayer.marketValueEur)}</dd>
          </dl>
          <a
            href={realPlayer.profileUrl}
            target="_blank"
            rel="noreferrer"
            className="text-body-sm text-accent-live hover:underline"
          >
            View on Transfermarkt ↗
          </a>
        </div>
      </CardContent>

      {actionError ? (
        <p className="px-ds-4 text-body-sm text-data-negative">{actionError}</p>
      ) : null}

      <CardFooter className="justify-end gap-ds-2 border-border-subtle bg-surface-800">
        <Button
          type="button"
          variant="outline"
          disabled={isBusy}
          onClick={() => setIsCorrectMatchOpen(true)}
          className="border-border-strong text-ink-primary hover:bg-surface-700"
        >
          Correct match
        </Button>
        <Button
          type="button"
          variant="destructive"
          disabled={isBusy}
          onClick={() => runAction("reject", () => onReject(review.id))}
        >
          {pendingAction === "reject" ? "Rejecting…" : "Reject"}
        </Button>
        <Button
          type="button"
          disabled={isBusy}
          onClick={() => runAction("approve", () => onApprove(review.id))}
          className="bg-brand text-on-brand hover:bg-brand-strong"
        >
          {pendingAction === "approve" ? "Approving…" : "Approve"}
        </Button>
      </CardFooter>

      <CorrectMatchDialog
        open={isCorrectMatchOpen}
        onOpenChange={setIsCorrectMatchOpen}
        initialQuery={syntheticPlayer.name}
        onSelect={(realPlayerId) => onReassign(review.id, realPlayerId)}
      />
    </Card>
  );
}
