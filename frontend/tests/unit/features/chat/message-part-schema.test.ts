import { describe, expect, it } from "vitest";

import { messagePartSchema } from "@/features/chat/schemas/message-part.schema";
import { samplePlayerForward, sampleTeam } from "@/features/chat/sample-data";

describe("messagePartSchema", () => {
  it("accepts a well-formed text part -- the only variant the live backend sends today", () => {
    const result = messagePartSchema.safeParse({ type: "text", content: "hello" });

    expect(result.success).toBe(true);
  });

  it("accepts a well-formed team_widget part matching the full TeamSummary shape", () => {
    const result = messagePartSchema.safeParse({ type: "team_widget", data: sampleTeam });

    expect(result.success).toBe(true);
  });

  it("rejects a team_widget part whose data is an untyped dict (today's backend stub shape)", () => {
    // src/chat/api/dtos/chat_dtos.py's TeamWidgetPart.data is currently `dict` --
    // this is exactly the shape a not-yet-implemented backend would send.
    const result = messagePartSchema.safeParse({ type: "team_widget", data: {} });

    expect(result.success).toBe(false);
  });

  it("accepts a player_widget part with a club profile and transfer path", () => {
    const result = messagePartSchema.safeParse({
      type: "player_widget",
      data: samplePlayerForward,
    });

    expect(result.success).toBe(true);
  });

  it("accepts a player_widget stored before club profile existed", () => {
    const legacy = Object.fromEntries(
      Object.entries(samplePlayerForward).filter(
        ([key]) => key !== "clubProfile" && key !== "transfers",
      ),
    );
    const result = messagePartSchema.safeParse({ type: "player_widget", data: legacy });

    expect(result.success).toBe(true);
  });

  it("rejects an unknown part type", () => {
    const result = messagePartSchema.safeParse({ type: "unknown_widget", data: {} });

    expect(result.success).toBe(false);
  });
});
