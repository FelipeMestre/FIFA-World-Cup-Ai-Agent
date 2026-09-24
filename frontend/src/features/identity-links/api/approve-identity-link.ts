import { fetchJson } from "@/lib/api/client";

export async function approveIdentityLink(linkId: number): Promise<void> {
  await fetchJson<unknown>(`/api/admin/identity-links/${linkId}/approve`, { method: "POST" });
}
