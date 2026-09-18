import { redirect } from "next/navigation";

import { hasSession } from "@/lib/auth/session";
import { ChatShell } from "@/features/chat";

/**
 * Thin routing shell -- composes the chat feature. `proxy.ts` already
 * redirects unauthenticated requests here to /login; this server check is
 * defense in depth in case this page is ever reached another way (e.g. a
 * proxy matcher change).
 */
export default async function HomePage() {
  if (!(await hasSession())) {
    redirect("/login");
  }

  return <ChatShell />;
}
