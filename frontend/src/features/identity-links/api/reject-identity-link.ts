import { fetchJson } from "@/lib/api/client";

export async function rejectIdentityLink(linkId: number): Promise<void> {
  await fetchJson<unknown>(`/api/admin/identity-links/${linkId}/reject`, { method: "POST" });
}
