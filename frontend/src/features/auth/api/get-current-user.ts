import "server-only";

import { currentUserSchema, type CurrentUser } from "@/features/auth/schemas/current-user.schema";
import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/**
 * Loads the signed-in user from FastAPI `GET /auth/me`. Returns null when
 * the session is missing or the payload is not a current-user body so the
 * home shell can keep rendering with a fallback label.
 */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  const response = await proxyBackendJson("/auth/me");
  if (!response.ok) {
    return null;
  }
  const parsed = currentUserSchema.safeParse(await response.json());
  return parsed.success ? parsed.data : null;
}
