import { fetchJson } from "@/lib/api/client";

export async function reassignIdentityLink(linkId: number, realPlayerId: number): Promise<void> {
  await fetchJson<unknown>(`/api/admin/identity-links/${linkId}/reassign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ real_player_id: realPlayerId }),
  });
}
