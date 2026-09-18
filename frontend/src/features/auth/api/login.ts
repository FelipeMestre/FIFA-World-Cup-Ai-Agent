import { login as loginRequest } from "@/lib/api/client";
import { loginSchema, type LoginFormValues } from "@/features/auth/schemas/login.schema";

/** Validates credentials, then calls the login Route Handler. */
export async function login(values: LoginFormValues): Promise<void> {
  const parsed = loginSchema.parse(values);
  await loginRequest(parsed);
}
