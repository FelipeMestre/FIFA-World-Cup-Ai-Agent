import { logout as logoutRequest } from "@/lib/api/client";

/** Clears the httpOnly session cookie via the logout Route Handler. */
export async function logout(): Promise<void> {
  await logoutRequest();
}
