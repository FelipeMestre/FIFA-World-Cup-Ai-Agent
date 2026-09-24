import { NextResponse } from "next/server";

import { isIdentityLinkId } from "@/features/identity-links/identity-link-id";
import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `POST /admin/identity-links/{id}/reassign` (the "correct match"
 * action, re-pointing a link at a different `real_player`).
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ linkId: string }> },
) {
  const { linkId } = await params;
  if (!isIdentityLinkId(linkId)) {
    return NextResponse.json({ detail: "Identity link not found" }, { status: 404 });
  }

  let body: { real_player_id?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }
  if (typeof body.real_player_id !== "number") {
    return NextResponse.json({ detail: "real_player_id is required" }, { status: 400 });
  }

  return proxyBackendJson(`/admin/identity-links/${linkId}/reassign`, {
    method: "POST",
    body: JSON.stringify({ real_player_id: body.real_player_id }),
  });
}
