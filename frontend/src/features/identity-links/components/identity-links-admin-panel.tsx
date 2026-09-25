"use client";

import { IdentityLinkRematchTrigger } from "@/features/identity-links/components/identity-link-rematch-trigger";
import { IdentityLinksReviewList } from "@/features/identity-links/components/identity-links-review-list";
import { useIdentityLinkRematch } from "@/features/identity-links/hooks/use-identity-link-rematch";
import { usePendingIdentityLinks } from "@/features/identity-links/hooks/use-pending-identity-links";

/** Composes this admin tab: the clean-rematch trigger above the identity
 * link review queue. Owns both hooks here (rather than each component
 * fetching independently) so a successful rematch can call the review
 * list's own `refresh()` -- a rematch wipes and regenerates every row, so
 * without this the list would keep showing now-deleted entries until a
 * manual refresh or reload.
 */
export function IdentityLinksAdminPanel() {
  const pendingLinks = usePendingIdentityLinks();
  const rematch = useIdentityLinkRematch(pendingLinks.refresh);

  return (
    <div className="flex flex-col gap-ds-4">
      <IdentityLinkRematchTrigger
        jobId={rematch.jobId}
        job={rematch.job}
        isTriggering={rematch.isTriggering}
        isRefreshing={rematch.isRefreshing}
        error={rematch.error}
        trigger={rematch.trigger}
        refresh={rematch.refresh}
      />

      <IdentityLinksReviewList
        status={pendingLinks.status}
        changeStatus={pendingLinks.changeStatus}
        reviews={pendingLinks.reviews}
        isLoading={pendingLinks.isLoading}
        loadError={pendingLinks.loadError}
        refresh={pendingLinks.refresh}
        approve={pendingLinks.approve}
        reject={pendingLinks.reject}
        reassign={pendingLinks.reassign}
        page={pendingLinks.page}
        totalPages={pendingLinks.totalPages}
        total={pendingLinks.total}
        pageSize={pendingLinks.pageSize}
        goToPage={pendingLinks.goToPage}
      />
    </div>
  );
}
