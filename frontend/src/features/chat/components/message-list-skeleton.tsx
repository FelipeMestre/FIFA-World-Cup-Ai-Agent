/**
 * Suspense fallback for the `/home/[conversationId]` server fetch -- a few
 * pulsing bubble shapes echoing `MessageList`'s question/answer turn layout
 * (user bubbles right-aligned, assistant bubbles left-aligned).
 */
export function MessageListSkeleton() {
  return (
    <div className="flex w-full flex-col gap-9 px-ds-6 py-ds-8" aria-hidden="true">
      <div className="flex flex-col gap-ds-5">
        <div className="flex justify-end">
          <div className="h-10 w-2/5 max-w-[420px] animate-pulse rounded-2xl bg-surface-800" />
        </div>
        <div className="flex flex-col gap-ds-2">
          <div className="h-4 w-4/5 max-w-[640px] animate-pulse rounded-md bg-surface-800" />
          <div className="h-4 w-3/5 max-w-[520px] animate-pulse rounded-md bg-surface-800" />
          <div className="h-4 w-2/5 max-w-[360px] animate-pulse rounded-md bg-surface-800" />
        </div>
      </div>
      <div className="flex flex-col gap-ds-5">
        <div className="flex justify-end">
          <div className="h-10 w-1/3 max-w-[320px] animate-pulse rounded-2xl bg-surface-800" />
        </div>
        <div className="flex flex-col gap-ds-2">
          <div className="h-4 w-3/5 max-w-[520px] animate-pulse rounded-md bg-surface-800" />
          <div className="h-4 w-1/2 max-w-[420px] animate-pulse rounded-md bg-surface-800" />
        </div>
      </div>
    </div>
  );
}
