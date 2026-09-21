import { redirect } from "next/navigation";

/**
 * The root route has no page of its own: `proxy.ts` sends signed-out
 * visitors to /login, and everyone else lands on /home.
 */
export default function RootPage() {
  redirect("/home");
}
