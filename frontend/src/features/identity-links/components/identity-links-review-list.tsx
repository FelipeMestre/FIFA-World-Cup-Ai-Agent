"use client";

import { Button } from "@/components/ui/button";
import { IdentityLinkReviewCard } from "@/features/identity-links/components/identity-link-review-card";
import { usePendingIdentityLinks } from "@/features/identity-links/hooks/use-pending-identity-links";

/** Admin-only review queue: every `player_identity_link` still `pending`,
 * with approve / reject / correct-match actions per row.
 */
export function IdentityLinksReviewList() {
  const { reviews, isLoading, loadError, refresh, approve, reject, reassign } =
    usePendingIdentityLinks();

  return (
    <div className="flex flex-col gap-ds-4">
      <div className="flex items-center justify-between gap-ds-3">
        <div>
          <h1 className="text-heading-lg">Identity link review</h1>
          <p className="text-body-sm text-ink-secondary">
            Doubtful matches between the WC2026 roster and Transfermarkt need a decision here.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={() => void refresh()}
          disabled={isLoading}
          className="border-border-strong text-ink-primary hover:bg-surface-700"
        >
          {isLoading ? "Refreshing…" : "Refresh"}
        </Button>
      </div>

      {loadError ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-4 text-body-sm text-data-negative">
          {loadError}
        </p>
      ) : null}

      {!isLoading && !loadError && reviews.length === 0 ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-6 text-center text-body-md text-ink-secondary">
          No pending matches. Everything from the last Transfermarkt sync has been reviewed.
        </p>
      ) : null}

      {isLoading && reviews.length === 0 ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-6 text-center text-body-md text-ink-secondary">
          Loading pending matches…
        </p>
      ) : null}

      <div className="flex flex-col gap-ds-3">
        {reviews.map((review) => (
          <IdentityLinkReviewCard
            key={review.id}
            review={review}
            onApprove={approve}
            onReject={reject}
            onReassign={reassign}
          />
        ))}
      </div>
    </div>
  );
}
