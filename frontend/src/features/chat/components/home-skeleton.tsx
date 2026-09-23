/**
 * Suspense fallback for `HomeLayout`'s auth-gated `<AuthedHomeShell>` --
 * visible only for the length of the same-server `hasSession()` cookie
 * read, so it stays a loose approximation of `HomeShell`'s layout (sidebar
 * column, header bar, content area) rather than a pixel-perfect match.
 */
export function HomeSkeleton() {
  return (
    <div className="flex h-dvh flex-col bg-surface-950" aria-hidden="true">
      <div className="flex min-h-0 grow">
        {/* Sidebar column */}
        <div className="hidden w-64 shrink-0 flex-col gap-ds-6 border-r border-border-subtle bg-surface-900 p-ds-4 md:flex">
          <div className="h-8 w-28 animate-pulse rounded-md bg-surface-700" />
          <div className="h-9 w-full animate-pulse rounded-lg bg-surface-800" />
          <div className="flex flex-col gap-ds-2">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="h-8 w-full animate-pulse rounded-md bg-surface-800" />
            ))}
          </div>
        </div>

        {/* Main content column */}
        <div className="flex min-h-0 min-w-0 grow flex-col">
          <div className="hidden h-16 shrink-0 items-center justify-end border-b border-border-subtle px-ds-6 md:flex">
            <div className="h-8 w-44 animate-pulse rounded-full bg-surface-800" />
          </div>
          <div className="flex flex-1 flex-col items-center justify-center gap-ds-6 px-ds-8">
            <div className="h-6 w-56 animate-pulse rounded-full bg-surface-800" />
            <div className="h-10 w-full max-w-[560px] animate-pulse rounded-lg bg-surface-800" />
            <div className="h-32 w-full max-w-[760px] animate-pulse rounded-2xl bg-surface-800" />
          </div>
        </div>
      </div>
    </div>
  );
}
