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

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE_NAME);

  if (pathname === "/" && !hasSession) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (pathname === "/login" && hasSession) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/login"],
};
