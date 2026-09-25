import { IdentityLinksAdminPanel } from "@/features/identity-links";

// @next-codemod-ignore Cache Components adoption: this segment temporarily allows blocking.
// Remove this opt-out after verifying the segment passes validation without it.
// See: https://nextjs.org/docs/app/guides/migrating-to-cache-components
export const instant = false;

/** Thin routing shell -- composes the identity-links feature's admin panel
 * (clean-rematch trigger + review list). */
export default function IdentityLinksPage() {
  return <IdentityLinksAdminPanel />;
}
