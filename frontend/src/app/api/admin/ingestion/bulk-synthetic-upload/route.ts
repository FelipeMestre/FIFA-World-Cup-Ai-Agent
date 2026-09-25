import { NextResponse } from "next/server";

import { proxyBackendMultipart } from "@/lib/api/proxy-backend-multipart";

/** Proxies `POST /admin/ingestion/bulk-synthetic-upload`, which resolves each
 * uploaded file's target table from its filename, queues every accepted file
 * as one FK-safe ordered job, and returns per-file accept/reject results.
 * The incoming `multipart/form-data` request's `FormData` (field name
 * `files`, repeated) is forwarded to the backend as-is -- there is nothing to
 * transform, the field name already matches what the backend expects.
 */
export async function POST(request: Request) {
  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    // Missing/non-multipart body -- `Request.formData()` throws rather than
    // returning an empty result, so this is caught explicitly instead of
    // surfacing as an unhandled 500 (mirrors the JSON routes' own
    // try/catch-and-default-gracefully handling of a malformed body).
    return NextResponse.json({ detail: "Expected a multipart/form-data body" }, { status: 400 });
  }

  return proxyBackendMultipart("/admin/ingestion/bulk-synthetic-upload", formData);
}
