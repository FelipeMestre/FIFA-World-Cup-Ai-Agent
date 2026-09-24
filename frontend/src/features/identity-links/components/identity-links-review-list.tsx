"use client";

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { IdentityLinkReviewCard } from "@/features/identity-links/components/identity-link-review-card";
import { PendingLinksPaginator } from "@/features/identity-links/components/pending-links-paginator";
import { usePendingIdentityLinks } from "@/features/identity-links/hooks/use-pending-identity-links";
import type { IdentityLinkReviewStatus } from "@/features/identity-links/types";

const STATUS_FILTERS: { value: IdentityLinkReviewStatus; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

/** Admin-only review queue: `player_identity_link`s filtered to one review
 * status at a time, with approve / reject / correct-match actions per row,
 * 50 to a page.
 */
export function IdentityLinksReviewList() {
  const {
    status,
    changeStatus,
    reviews,
    isLoading,
    loadError,
    refresh,
    approve,
    reject,
    reassign,
    page,
    totalPages,
    total,
    pageSize,
    goToPage,
  } = usePendingIdentityLinks();

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

      <Tabs
        value={status}
        onValueChange={(value) => changeStatus(value as IdentityLinkReviewStatus)}
      >
        <TabsList>
          {STATUS_FILTERS.map((filter) => (
            <TabsTrigger key={filter.value} value={filter.value}>
              {filter.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {loadError ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-4 text-body-sm text-data-negative">
          {loadError}
        </p>
      ) : null}

      {!isLoading && !loadError && reviews.length === 0 ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-6 text-center text-body-md text-ink-secondary">
          No {status} matches.
        </p>
      ) : null}

      {isLoading && reviews.length === 0 ? (
        <p className="rounded-lg border border-border-subtle bg-surface-800 p-ds-6 text-center text-body-md text-ink-secondary">
          Loading {status} matches…
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

      <PendingLinksPaginator
        page={page}
        totalPages={totalPages}
        total={total}
        pageSize={pageSize}
        isLoading={isLoading}
        onPageChange={goToPage}
      />
    </div>
  );
}
