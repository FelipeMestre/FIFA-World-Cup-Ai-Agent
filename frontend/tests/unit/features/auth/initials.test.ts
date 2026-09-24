import { describe, expect, it } from "vitest";

import { initialsFromName } from "@/features/auth/initials";

describe("initialsFromName", () => {
  it("uses the first letter of the first two words", () => {
    expect(initialsFromName("Ada Scout")).toBe("AS");
  });

  it("uses up to two letters of a single word", () => {
    expect(initialsFromName("Ada")).toBe("AD");
  });

  it("returns a placeholder for a blank name", () => {
    expect(initialsFromName("   ")).toBe("?");
  });
});
