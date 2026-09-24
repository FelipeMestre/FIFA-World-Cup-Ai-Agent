import { Suspense, type ReactNode } from "react";
import { redirect } from "next/navigation";

import { HomeShell } from "@/features/chat/components/home-shell";
import { HomeSkeleton } from "@/features/chat/components/home-skeleton";
import { hasSession } from "@/lib/auth/session";

/**
 * Parent of both `/home` and `/home/[conversationId]`. The chat shell lives
 * here so a first send that only changes the URL does not remount it.
 * `{children}` now renders *inside* HomeShell (not beside it) so a
 * server-fetched conversation replay (see [conversationId]/page.tsx) has a
 * path into HomeShell's chat state via ThreadHydrationProvider.
 */
export default function HomeLayout({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<HomeSkeleton />}>
      <AuthedHomeShell>{children}</AuthedHomeShell>
    </Suspense>
  );
}

async function AuthedHomeShell({ children }: { children: ReactNode }) {
  if (!(await hasSession())) {
    redirect("/login");
  }
  return <HomeShell>{children}</HomeShell>;
}
