import { SyncJobsPanel } from "@/features/ingestion";

// @next-codemod-ignore Cache Components adoption: this segment temporarily allows blocking.
// Remove this opt-out after verifying the segment passes validation without it.
// See: https://nextjs.org/docs/app/guides/migrating-to-cache-components
export const instant = false;

/** Thin routing shell -- composes the ingestion feature's sync-jobs panel. */
export default function SyncJobsPage() {
  return <SyncJobsPanel />;
}
