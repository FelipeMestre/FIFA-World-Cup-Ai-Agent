import { NextResponse } from "next/server";

import { BACKEND_API_URL } from "@/lib/api/config";
import { getSessionToken } from "@/lib/auth/session";

const UNREACHABLE = "Could not reach the World Cup AI Scout backend";

/**
 * Authenticated JSON proxy to FastAPI. The browser never sees the backend
 * URL or the bearer token -- Route Handlers call this instead.
 */
export async function proxyBackendJson(
  path: string,
  init: RequestInit = {},
): Promise<NextResponse> {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_API_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch {
    return NextResponse.json({ detail: UNREACHABLE }, { status: 502 });
  }

  const payload: { detail?: string } | null = await backendResponse.json().catch(() => null);
  if (!backendResponse.ok) {
    return NextResponse.json(
      { detail: payload?.detail ?? "Request failed" },
      { status: backendResponse.status },
    );
  }

  return NextResponse.json(payload);
}
