import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Auth gate. Next.js 16 renamed `middleware.ts` to `proxy.ts` (same
 * behavior, see node_modules/next/dist/docs/.../proxy.md) -- this is the
 * replacement, not a new pattern.
 *
 * This only checks for the *presence* of the session cookie for a fast
 * redirect; the cookie's JWT is still verified by the FastAPI backend on
 * every request made through app/api/chat/messages/route.ts. Presence-only
 * checks here are a UX shortcut, not the authorization boundary.
 */
const SESSION_COOKIE_NAME = "fai_session";
const PUBLIC_PATHS = new Set(["/login"]);
const SIGNED_IN_LANDING = "/home";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE_NAME);

  if (!hasSession && !PUBLIC_PATHS.has(pathname)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // `/` has no page of its own, and a signed-in visitor has no use for the
  // login form.
  if (hasSession && (pathname === "/" || pathname === "/login")) {
    return NextResponse.redirect(new URL(SIGNED_IN_LANDING, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/home", "/login"],
};
