"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { approveIdentityLink } from "@/features/identity-links/api/approve-identity-link";
import { listIdentityLinks } from "@/features/identity-links/api/list-identity-links";
import { reassignIdentityLink } from "@/features/identity-links/api/reassign-identity-link";
import { rejectIdentityLink } from "@/features/identity-links/api/reject-identity-link";
import type { IdentityLinkReview, IdentityLinkReviewStatus } from "@/features/identity-links/types";

export const PENDING_LINKS_PAGE_SIZE = 50;

/** Reviewing (approve/reject/reassign) always takes a pending link out of
 * `pending` status, so every action here re-fetches the current page
 * afterwards rather than splicing the item out of local state -- with
 * pagination, a local splice would desync from the server's total/page
 * count (e.g. the last item on a later page being removed should pull the
 * next page's first item up, not just shrink this page by one).
 */
export function usePendingIdentityLinks() {
  const [status, setStatus] = useState<IdentityLinkReviewStatus>("pending");
  const [page, setPage] = useState(1);
  const [reviews, setReviews] = useState<IdentityLinkReview[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PENDING_LINKS_PAGE_SIZE));

  // Guards against out-of-order responses: switching status/page issues a
  // new request before a slower in-flight one resolves, and without this a
  // stale response landing last would silently overwrite the current view
  // with the wrong status's data.
  const latestRequestRef = useRef(0);

  const fetchPage = useCallback(
    async (targetStatus: IdentityLinkReviewStatus, targetPage: number) => {
      const requestId = ++latestRequestRef.current;
      setIsLoading(true);
      try {
        const offset = (targetPage - 1) * PENDING_LINKS_PAGE_SIZE;
        const result = await listIdentityLinks(targetStatus, PENDING_LINKS_PAGE_SIZE, offset);
        if (requestId !== latestRequestRef.current) return;
        // A mutation on the last item of the last page can leave `targetPage`
        // past the new last page (e.g. rejecting the sole item on page 3 of
        // 3) -- fall back one page rather than showing an empty page with
        // more pages behind it.
        if (result.items.length === 0 && targetPage > 1 && result.total > 0) {
          const lastPage = Math.max(1, Math.ceil(result.total / PENDING_LINKS_PAGE_SIZE));
          setPage(lastPage);
          return;
        }
        setReviews(result.items);
        setTotal(result.total);
        setLoadError(null);
      } catch {
        if (requestId !== latestRequestRef.current) return;
        setLoadError("Couldn't load pending matches");
      } finally {
        if (requestId === latestRequestRef.current) setIsLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void fetchPage(status, page);
  }, [fetchPage, status, page]);

  const refresh = useCallback(() => fetchPage(status, page), [fetchPage, status, page]);

  const changeStatus = useCallback((targetStatus: IdentityLinkReviewStatus) => {
    setStatus(targetStatus);
    setPage(1);
  }, []);

  // Deliberately doesn't clamp against `totalPages` here: that value is
  // stale (defaults to 1) until the first page has actually loaded, which
  // would silently no-op a `goToPage(2)` called before then. The paginator
  // UI already disables Next past the known last page, and `fetchPage`
  // itself falls back a page if a target page turns out to be empty.
  const goToPage = useCallback((targetPage: number) => {
    setPage(Math.max(1, targetPage));
  }, []);

  const approve = useCallback(
    async (linkId: number) => {
      await approveIdentityLink(linkId);
      await refresh();
    },
    [refresh],
  );

  const reject = useCallback(
    async (linkId: number) => {
      await rejectIdentityLink(linkId);
      await refresh();
    },
    [refresh],
  );

  const reassign = useCallback(
    async (linkId: number, realPlayerId: number) => {
      await reassignIdentityLink(linkId, realPlayerId);
      await refresh();
    },
    [refresh],
  );

  return {
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
    pageSize: PENDING_LINKS_PAGE_SIZE,
    goToPage,
  };
}
