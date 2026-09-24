"use client";

import { useCallback, useEffect, useState } from "react";

import { approveIdentityLink } from "@/features/identity-links/api/approve-identity-link";
import { listPendingIdentityLinks } from "@/features/identity-links/api/list-pending-identity-links";
import { reassignIdentityLink } from "@/features/identity-links/api/reassign-identity-link";
import { rejectIdentityLink } from "@/features/identity-links/api/reject-identity-link";
import type { IdentityLinkReview } from "@/features/identity-links/types";

/** Reviewing (approve/reject/reassign) always takes a pending link out of
 * `pending` status, so every action here removes it from local state
 * instead of re-fetching the whole list.
 */
export function usePendingIdentityLinks() {
  const [reviews, setReviews] = useState<IdentityLinkReview[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const items = await listPendingIdentityLinks();
      setReviews(items);
      setLoadError(null);
    } catch {
      setLoadError("Couldn't load pending matches");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const removeReviewed = useCallback((linkId: number) => {
    setReviews((prev) => prev.filter((review) => review.id !== linkId));
  }, []);

  const approve = useCallback(
    async (linkId: number) => {
      await approveIdentityLink(linkId);
      removeReviewed(linkId);
    },
    [removeReviewed],
  );

  const reject = useCallback(
    async (linkId: number) => {
      await rejectIdentityLink(linkId);
      removeReviewed(linkId);
    },
    [removeReviewed],
  );

  const reassign = useCallback(
    async (linkId: number, realPlayerId: number) => {
      await reassignIdentityLink(linkId, realPlayerId);
      removeReviewed(linkId);
    },
    [removeReviewed],
  );

  return { reviews, isLoading, loadError, refresh, approve, reject, reassign };
}
