import { NextResponse } from "next/server";

import { BACKEND_API_URL } from "@/lib/api/config";
import { getSessionToken } from "@/lib/auth/session";

const UNREACHABLE = "Could not reach the World Cup AI Scout backend";

/**
 * Authenticated `multipart/form-data` proxy to FastAPI, for routes that
 * accept file uploads. Mirrors `proxyBackendJson`'s auth handling -- the
 * browser never sees the backend URL or the bearer token -- but forwards the
 * caller's `FormData` as the request body instead of a JSON string, and sets
 * no `Content-Type` header itself: `fetch` derives the multipart boundary
 * from the `FormData` instance, and a hand-set header here would omit it and
 * break the backend's parser.
 *
 * Unlike `proxyBackendJson` (which normalizes every error to a plain
 * `{ detail: string }`), this forwards the backend's JSON body verbatim on
 * every status. The bulk-upload endpoint's 400 body carries a structured
 * `detail.files` per-file rejection list the caller needs to render, not
 * just a message string, so collapsing it here would lose information no
 * other response provides.
 */
export async function proxyBackendMultipart(
  path: string,
  formData: FormData,
): Promise<NextResponse> {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_API_URL}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
  } catch {
    return NextResponse.json({ detail: UNREACHABLE }, { status: 502 });
  }

  const payload: unknown = await backendResponse.json().catch(() => null);
  if (payload === null) {
    return NextResponse.json(
      { detail: "Request failed" },
      { status: backendResponse.status || 502 },
    );
  }

  return NextResponse.json(payload, { status: backendResponse.status });
}
