import { describe, expect, it } from "vitest";

import { groupConversations } from "@/features/chat/group-conversations";
import type { ConversationSummary } from "@/features/chat/types";

function summary(
  id: string,
  title: string,
  updatedAt: string,
): ConversationSummary {
  return { id, title, updatedAt, createdAt: updatedAt, isGenerating: false };
}

describe("groupConversations", () => {
  const now = new Date("2026-09-22T18:00:00");

  it("puts same-local-day rows in Today and the rest in Earlier", () => {
    const grouped = groupConversations(
      [
        summary("a", "Today chat", "2026-09-22T10:00:00"),
        summary("b", "Yesterday", "2026-09-21T23:00:00"),
      ],
      now,
    );

    expect(grouped.today.map((row) => row.id)).toEqual(["a"]);
    expect(grouped.earlier.map((row) => row.id)).toEqual(["b"]);
  });

  it("treats an unparseable timestamp as Earlier", () => {
    const grouped = groupConversations(
      [summary("c", "Broken", "not-a-date")],
      now,
    );
    expect(grouped.today).toEqual([]);
    expect(grouped.earlier.map((row) => row.id)).toEqual(["c"]);
  });
});
