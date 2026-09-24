"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Paginator for the pending identity-link review queue (50 rows/page). */
export function PendingLinksPaginator({
  page,
  totalPages,
  total,
  pageSize,
  isLoading,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  isLoading: boolean;
  onPageChange: (page: number) => void;
}) {
  if (total === 0) return null;

  const firstRow = (page - 1) * pageSize + 1;
  const lastRow = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between gap-ds-3 border-t border-border-subtle pt-ds-3">
      <span className="text-body-sm text-ink-muted">
        Showing {firstRow}–{lastRow} of {total}
      </span>
      <div className="flex items-center gap-ds-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isLoading || page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="border-border-strong text-ink-primary hover:bg-surface-700"
        >
          <ChevronLeft className="size-4" aria-hidden />
          Previous
        </Button>
        <span className="text-body-sm text-ink-secondary">
          Page {page} of {totalPages}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isLoading || page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="border-border-strong text-ink-primary hover:bg-surface-700"
        >
          Next
          <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>
    </div>
  );
}
