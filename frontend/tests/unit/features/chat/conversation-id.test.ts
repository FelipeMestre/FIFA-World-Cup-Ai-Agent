import { describe, expect, it } from "vitest";

import {
  isConversationId,
  parseHomeConversationSegments,
} from "@/features/chat/conversation-id";

describe("conversation-id", () => {
  it("accepts a UUID and rejects other path segments", () => {
    expect(isConversationId("550e8400-e29b-41d4-a716-446655440000")).toBe(true);
    expect(isConversationId("not-a-uuid")).toBe(false);
  });

  it("parses the optional /home catch-all segment", () => {
    expect(parseHomeConversationSegments(undefined)).toEqual({ status: "empty" });
    expect(parseHomeConversationSegments([])).toEqual({ status: "empty" });
    expect(
      parseHomeConversationSegments(["550e8400-e29b-41d4-a716-446655440000"]),
    ).toEqual({ status: "ok", id: "550e8400-e29b-41d4-a716-446655440000" });
    expect(parseHomeConversationSegments(["nope"])).toEqual({ status: "invalid" });
    expect(
      parseHomeConversationSegments(["550e8400-e29b-41d4-a716-446655440000", "extra"]),
    ).toEqual({ status: "invalid" });
  });
});
