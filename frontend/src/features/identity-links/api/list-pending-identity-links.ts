import { fetchJson } from "@/lib/api/client";
import {
  identityLinkReviewListSchema,
  toIdentityLinkReview,
} from "@/features/identity-links/schemas/identity-link-review.schema";
import type { IdentityLinkReview } from "@/features/identity-links/types";

export async function listPendingIdentityLinks(): Promise<IdentityLinkReview[]> {
  const payload = await fetchJson<unknown>("/api/admin/identity-links/pending");
  return identityLinkReviewListSchema.parse(payload).map(toIdentityLinkReview);
}
