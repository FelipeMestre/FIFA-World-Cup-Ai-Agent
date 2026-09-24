import { Suspense, type ReactNode } from "react";
import { redirect } from "next/navigation";

import { AdminHeader } from "@/components/layout/admin-header";
import { getCurrentUser } from "@/features/auth/api/get-current-user";
import { hasSession } from "@/lib/auth/session";

// @next-codemod-ignore Cache Components adoption: this segment temporarily allows blocking.
// Remove this opt-out after verifying the segment passes validation without it.
// See: https://nextjs.org/docs/app/guides/migrating-to-cache-components
export const instant = false;

/** Gates every `(admin)` route on `is_admin` before rendering. A signed-out
 * visitor goes to `/login`; a signed-in non-admin goes back to `/home`
 * rather than seeing a 403 -- the backend still enforces `require_admin`
 * on every admin endpoint regardless, this is just the UX-level guard.
 */
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<AdminSkeleton />}>
      <AuthedAdminShell>{children}</AuthedAdminShell>
    </Suspense>
  );
}

async function AuthedAdminShell({ children }: { children: ReactNode }) {
  if (!(await hasSession())) {
    redirect("/login");
  }
  const user = await getCurrentUser();
  if (!user?.is_admin) {
    redirect("/home");
  }

  return (
    <div className="flex min-h-dvh flex-col bg-surface-950 text-ink-primary">
      <AdminHeader userName={user.name} />
      <main className="mx-auto w-full max-w-5xl flex-1 px-ds-4 py-ds-6 md:px-ds-6">
        {children}
      </main>
    </div>
  );
}

function AdminSkeleton() {
  return <div className="min-h-dvh bg-surface-950" />;
}
