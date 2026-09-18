import { describe, expect, it } from "vitest";

import { validateLoginForm } from "@/features/auth/schemas/login.schema";

describe("validateLoginForm", () => {
  it("returns no errors for a valid email and non-empty password", () => {
    const errors = validateLoginForm({ email: "admin@football.ai", password: "local-dev-password" });

    expect(errors).toEqual({});
  });

  it("flags a missing email", () => {
    const errors = validateLoginForm({ email: "", password: "x" });

    expect(errors.email).toBeDefined();
    expect(errors.password).toBeUndefined();
  });

  it("flags a malformed email", () => {
    const errors = validateLoginForm({ email: "not-an-email", password: "x" });

    expect(errors.email).toMatch(/valid email/i);
  });

  it("flags a missing password", () => {
    const errors = validateLoginForm({ email: "admin@football.ai", password: "" });

    expect(errors.password).toBeDefined();
    expect(errors.email).toBeUndefined();
  });
});
