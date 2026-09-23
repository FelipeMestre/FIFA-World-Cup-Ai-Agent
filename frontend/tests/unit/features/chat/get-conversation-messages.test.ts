import { describe, expect, it } from "vitest";

import { parseConversationReplay } from "@/features/chat/api/get-conversation-messages";

const CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440000";

describe("parseConversationReplay", () => {
  it("leaves messages untouched when there is no last_turn_failure", () => {
    const replay = parseConversationReplay({
      conversation_id: CONVERSATION_ID,
      title: "A conversation",
      messages: [{ role: "user", parts: [{ type: "text", content: "Hi" }], created_at: "now" }],
      last_turn_failure: null,
    });

    expect(replay.messages).toHaveLength(1);
    expect(replay.messages[0]?.error).toBeUndefined();
  });

  it("appends a synthetic error-bearing assistant message when last_turn_failure is set", () => {
    const replay = parseConversationReplay({
      conversation_id: CONVERSATION_ID,
      title: "A conversation",
      messages: [
        { role: "user", parts: [{ type: "text", content: "Hi" }], created_at: "now" },
      ],
      last_turn_failure: "The chat assistant is temporarily unavailable",
    });

    expect(replay.messages).toHaveLength(2);
    const failureMessage = replay.messages[1];
    expect(failureMessage?.role).toBe("assistant");
    expect(failureMessage?.parts).toEqual([]);
    expect(failureMessage?.error).toBe("The chat assistant is temporarily unavailable");
  });

  it("tolerates a response with no last_turn_failure field at all (older backend contract)", () => {
    const replay = parseConversationReplay({
      conversation_id: CONVERSATION_ID,
      title: "A conversation",
      messages: [],
    });

    expect(replay.messages).toHaveLength(0);
  });
});
