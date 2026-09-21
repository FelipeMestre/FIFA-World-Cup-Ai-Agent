import { redirect } from "next/navigation";

import { hasSession } from "@/lib/auth/session";
import { HomeShell } from "@/features/chat/components/home-shell";

/**
 * The landing page (Main.dc.html): hero, composer and suggested prompts.
 * Submitting here hands the question to /chat via `?prompt=`. `proxy.ts`
 * already gates this route; the server check is defense in depth in case it
 * is ever reached another way (e.g. a proxy matcher change).
 */
export default async function HomePage() {
  if (!(await hasSession())) {
    redirect("/login");
  }

  return <HomeShell />;
}
