import { describe, expect, it } from "vitest";

import {
  conversationSummarySchema,
  toConversationSummary,
} from "@/features/chat/schemas/conversation.schema";

describe("conversationSummarySchema / toConversationSummary", () => {
  it("maps is_generating through to isGenerating", () => {
    const row = conversationSummarySchema.parse({
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "A conversation",
      updated_at: "2026-09-23T10:00:00Z",
      created_at: "2026-09-23T09:00:00Z",
      is_generating: true,
    });

    expect(toConversationSummary(row).isGenerating).toBe(true);
  });

  it("defaults is_generating to false when the backend omits it", () => {
    const row = conversationSummarySchema.parse({
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "A conversation",
      updated_at: "2026-09-23T10:00:00Z",
      created_at: "2026-09-23T09:00:00Z",
    });

    expect(toConversationSummary(row).isGenerating).toBe(false);
  });

  it("maps a category icon through to the domain summary", () => {
    const row = conversationSummarySchema.parse({
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "A conversation",
      updated_at: "2026-09-23T10:00:00Z",
      created_at: "2026-09-23T09:00:00Z",
      icon: "player",
    });

    expect(toConversationSummary(row).icon).toBe("player");
  });

  it("defaults icon to null when the backend omits it (not yet categorized)", () => {
    const row = conversationSummarySchema.parse({
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "A conversation",
      updated_at: "2026-09-23T10:00:00Z",
      created_at: "2026-09-23T09:00:00Z",
    });

    expect(toConversationSummary(row).icon).toBeNull();
  });

  it("preserves an explicit null icon", () => {
    const row = conversationSummarySchema.parse({
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "A conversation",
      updated_at: "2026-09-23T10:00:00Z",
      created_at: "2026-09-23T09:00:00Z",
      icon: null,
    });

    expect(toConversationSummary(row).icon).toBeNull();
  });
});
