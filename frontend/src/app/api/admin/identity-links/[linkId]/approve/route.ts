import { NextResponse } from "next/server";

import { isIdentityLinkId } from "@/features/identity-links/identity-link-id";
import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/** Proxies `POST /admin/identity-links/{id}/approve`. */
export async function POST(
  _request: Request,
  { params }: { params: Promise<{ linkId: string }> },
) {
  const { linkId } = await params;
  if (!isIdentityLinkId(linkId)) {
    return NextResponse.json({ detail: "Identity link not found" }, { status: 404 });
  }

  return proxyBackendJson(`/admin/identity-links/${linkId}/approve`, { method: "POST" });
}
