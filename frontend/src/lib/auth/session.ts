import "server-only";

import { cookies } from "next/headers";

/**
 * httpOnly session cookie helpers. The JWT issued by the FastAPI backend
 * lives only in this cookie -- it is never sent to client JS, which is why
 * `app/api/auth/login/route.ts` and `app/api/conversations/**` exist as a
 * server-side proxy in front of the
 * backend instead of the browser calling the backend directly.
 */
const SESSION_COOKIE_NAME = "fai_session";

export async function getSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(SESSION_COOKIE_NAME)?.value ?? null;
}

export async function setSessionToken(
  token: string,
  expiresInMinutes: number,
): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: expiresInMinutes * 60,
  });
}

export async function clearSessionToken(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, "", {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
}

export async function hasSession(): Promise<boolean> {
  return (await getSessionToken()) !== null;
}
