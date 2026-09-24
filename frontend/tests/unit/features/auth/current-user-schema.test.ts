import { describe, expect, it } from "vitest";

import { currentUserSchema } from "@/features/auth/schemas/current-user.schema";

describe("currentUserSchema", () => {
  it("accepts a current-user payload from GET /auth/me", () => {
    const user = currentUserSchema.parse({
      id: 1,
      email: "ada@football.ai",
      name: "Ada Scout",
      is_admin: false,
    });

    expect(user.name).toBe("Ada Scout");
  });
});
