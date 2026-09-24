import { fetchJson } from "@/lib/api/client";
import {
  pendingIdentityLinksPageSchema,
  toPendingIdentityLinksPage,
} from "@/features/identity-links/schemas/identity-link-review.schema";
import type { IdentityLinkReviewStatus, PendingIdentityLinksPage } from "@/features/identity-links/types";

export async function listIdentityLinks(
  status: IdentityLinkReviewStatus,
  limit: number,
  offset: number,
): Promise<PendingIdentityLinksPage> {
  const payload = await fetchJson<unknown>(
    `/api/admin/identity-links?status=${status}&limit=${limit}&offset=${offset}`,
  );
  return toPendingIdentityLinksPage(pendingIdentityLinksPageSchema.parse(payload));
}
