import { NextResponse } from "next/server";

import { clearSessionToken } from "@/lib/auth/session";

/**
 * Drops the httpOnly session cookie. The FastAPI JWT is not revoked
 * server-side (it is short-lived); clearing the cookie is what signs the
 * browser out of this app.
 */
export async function POST() {
  await clearSessionToken();
  return NextResponse.json({ ok: true });
}
