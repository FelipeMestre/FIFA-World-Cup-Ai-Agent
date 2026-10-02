import { describe, expect, it } from "vitest";

import { touchConversation } from "@/features/chat/touch-conversation";
import type { ConversationSummary } from "@/features/chat/types";

function row(id: string, updatedAt: string): ConversationSummary {
  return {
    id,
    title: `title-${id}`,
    icon: "team",
    updatedAt,
    createdAt: "2026-09-01T00:00:00Z",
    isGenerating: false,
  };
}

describe("touchConversation", () => {
  const rows = [
    row("a", "2026-09-22T11:00:00Z"),
    row("b", "2026-09-22T10:00:00Z"),
    row("c", "2026-09-01T10:00:00Z"),
  ];

  it("moves the row to the top with the new updatedAt, keeping other fields", () => {
    const result = touchConversation(rows, "c", "2026-09-24T09:00:00Z");

    expect(result.map((r) => r.id)).toEqual(["c", "a", "b"]);
    expect(result[0]).toEqual({ ...rows[2], updatedAt: "2026-09-24T09:00:00Z" });
  });

  it("is idempotent when the same event is applied twice", () => {
    const once = touchConversation(rows, "c", "2026-09-24T09:00:00Z");
    const twice = touchConversation(once, "c", "2026-09-24T09:00:00Z");

    expect(twice).toEqual(once);
  });

  it("is a no-op for an id that is not in the list", () => {
    expect(touchConversation(rows, "missing", "2026-09-24T09:00:00Z")).toBe(rows);
  });

  it("ignores a stale event older than the row's current updatedAt", () => {
    expect(touchConversation(rows, "a", "2026-09-20T00:00:00Z")).toBe(rows);
  });
});
