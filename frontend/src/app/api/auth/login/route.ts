import { NextResponse } from "next/server";

import { BACKEND_API_URL } from "@/lib/api/config";
import { setSessionToken } from "@/lib/auth/session";

interface BackendLoginResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
}

interface BackendErrorResponse {
  detail?: string;
}

/**
 * Proxies to the FastAPI backend's `/auth/login`. On success, stores the JWT
 * in an httpOnly cookie server-side and returns only a success flag -- the
 * token itself never reaches client JS.
 */
export async function POST(request: Request) {
  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  if (!body.email || !body.password) {
    return NextResponse.json(
      { detail: "Email and password are required" },
      { status: 400 },
    );
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: body.email, password: body.password }),
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach the World Cup AI Scout backend" },
      { status: 502 },
    );
  }

  if (!backendResponse.ok) {
    const errorPayload = (await backendResponse
      .json()
      .catch(() => null)) as BackendErrorResponse | null;
    return NextResponse.json(
      { detail: errorPayload?.detail ?? "Invalid email or password" },
      { status: backendResponse.status },
    );
  }

  const payload = (await backendResponse.json()) as BackendLoginResponse;
  await setSessionToken(payload.access_token, payload.expires_in_minutes);

  return NextResponse.json({ ok: true });
}
