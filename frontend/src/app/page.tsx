import { redirect } from "next/navigation";

// @next-codemod-ignore Cache Components adoption: this segment temporarily allows blocking.
// Remove this opt-out after verifying the segment passes validation without it.
// See: https://nextjs.org/docs/app/guides/migrating-to-cache-components
export const instant = false;

/**
 * The root route has no page of its own: `proxy.ts` sends signed-out
 * visitors to /login, and everyone else lands on /home.
 */
export default function RootPage() {
  redirect("/home");
}
