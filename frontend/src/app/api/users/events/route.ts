import { NextResponse } from "next/server";

import { BACKEND_API_URL } from "@/lib/api/config";
import { getSessionToken } from "@/lib/auth/session";

const UNREACHABLE = "Could not reach the World Cup AI Scout backend";

/**
 * Streaming proxy to `GET /users/events` (SSE) -- the authenticated user's
 * own account-wide event stream. Unlike `proxyBackendJson`, this never
 * awaits or re-serializes the backend body -- doing so would buffer the
 * entire (deliberately infinite) stream before anything reaches the
 * browser. The backend response's `body` is a `ReadableStream`; it's
 * returned as-is. Mirrors
 * `app/api/conversations/[conversationId]/events/route.ts` exactly, minus
 * the path param and its id validation (there is nothing to validate --
 * this stream has no conversation id).
 *
 * No route segment config is set here: with this project's `cacheComponents`
 * flag on (`next.config.ts`), the `dynamic`/`revalidate`/`fetchCache` segment
 * exports are removed entirely (Next.js 16 -- see
 * `node_modules/next/dist/docs/.../route-segment-config`), not just
 * deprecated, so setting one would break the build. None is needed anyway:
 * reading the session cookie (`getSessionToken`) and the incoming
 * `Last-Event-ID` header already makes this route run per-request.
 */
export async function GET(request: Request) {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const headers: HeadersInit = {
    Authorization: `Bearer ${token}`,
    Accept: "text/event-stream",
  };
  const lastEventId = request.headers.get("Last-Event-ID");
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_API_URL}/users/events`, { headers });
  } catch {
    return NextResponse.json({ detail: UNREACHABLE }, { status: 502 });
  }

  if (!backendResponse.ok || !backendResponse.body) {
    const payload: { detail?: string } | null = await backendResponse.json().catch(() => null);
    return NextResponse.json(
      { detail: payload?.detail ?? "Could not open the live event stream" },
      { status: backendResponse.status || 502 },
    );
  }

  return new Response(backendResponse.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
