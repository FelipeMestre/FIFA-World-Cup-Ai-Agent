import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const listConversationsMock = vi.fn();
vi.mock("@/features/chat/api/list-conversations", () => ({
  listConversations: (...args: unknown[]) => listConversationsMock(...args),
}));

const updateConversationTitleMock = vi.fn();
vi.mock("@/features/chat/api/update-conversation-title", () => ({
  updateConversationTitle: (...args: unknown[]) => updateConversationTitleMock(...args),
}));

const { useConversationList } = await import(
  "@/features/chat/hooks/use-conversation-list"
);

describe("useConversationList", () => {
  beforeEach(() => {
    listConversationsMock.mockReset();
    updateConversationTitleMock.mockReset();
  });

  it("loads the signed-in user's conversations", async () => {
    listConversationsMock.mockResolvedValue([
      {
        id: "550e8400-e29b-41d4-a716-446655440000",
        title: "Argentina defence",
        updatedAt: "2026-09-22T10:00:00Z",
        createdAt: "2026-09-22T09:00:00Z",
      },
    ]);

    const { result } = renderHook(() => useConversationList());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.conversations[0]?.title).toBe("Argentina defence");
    expect(result.current.loadError).toBeNull();
  });

  it("surfaces a load error without crashing", async () => {
    listConversationsMock.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useConversationList());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.conversations).toEqual([]);
    expect(result.current.loadError).toBe("Couldn't load conversations");
  });

  it("renames a conversation and moves it to the top of the list", async () => {
    const first = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "Argentina defence",
      updatedAt: "2026-09-22T10:00:00Z",
      createdAt: "2026-09-22T09:00:00Z",
    };
    const second = {
      id: "660e8400-e29b-41d4-a716-446655440000",
      title: "France vs Spain",
      updatedAt: "2026-09-22T11:00:00Z",
      createdAt: "2026-09-22T11:00:00Z",
    };
    listConversationsMock.mockResolvedValue([second, first]);
    const renamed = {
      ...first,
      title: "Albiceleste shape",
      updatedAt: "2026-09-22T12:00:00Z",
    };
    updateConversationTitleMock.mockResolvedValue(renamed);

    const { result } = renderHook(() => useConversationList());
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.rename(first.id, "Albiceleste shape");
    });

    expect(updateConversationTitleMock).toHaveBeenCalledWith(first.id, "Albiceleste shape");
    expect(result.current.conversations.map((row) => row.id)).toEqual([first.id, second.id]);
    expect(result.current.conversations[0]?.title).toBe("Albiceleste shape");
  });

  it("applyConversationUpdate patches the matching row's title/icon in place, without touching others or refetching", async () => {
    const first = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "New chat",
      icon: null,
      updatedAt: "2026-09-22T10:00:00Z",
      createdAt: "2026-09-22T09:00:00Z",
    };
    const second = {
      id: "660e8400-e29b-41d4-a716-446655440000",
      title: "France vs Spain",
      icon: "match",
      updatedAt: "2026-09-22T11:00:00Z",
      createdAt: "2026-09-22T11:00:00Z",
    };
    listConversationsMock.mockResolvedValue([second, first]);

    const { result } = renderHook(() => useConversationList());
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.applyConversationUpdate(first.id, { title: "Argentina defence", icon: "team" });
    });

    expect(listConversationsMock).toHaveBeenCalledTimes(1);
    // Order preserved (unlike rename) -- this patches a row in place rather
    // than promoting it, since a background categorization event is not a
    // user-initiated action that should reorder the list.
    expect(result.current.conversations.map((row) => row.id)).toEqual([second.id, first.id]);
    const patched = result.current.conversations.find((row) => row.id === first.id);
    expect(patched?.title).toBe("Argentina defence");
    expect(patched?.icon).toBe("team");
    const untouched = result.current.conversations.find((row) => row.id === second.id);
    expect(untouched?.title).toBe("France vs Spain");
    expect(untouched?.icon).toBe("match");
  });

  it("applyConversationUpdate on an id not in the list is a no-op", async () => {
    const first = {
      id: "550e8400-e29b-41d4-a716-446655440000",
      title: "Argentina defence",
      icon: null,
      updatedAt: "2026-09-22T10:00:00Z",
      createdAt: "2026-09-22T09:00:00Z",
    };
    listConversationsMock.mockResolvedValue([first]);

    const { result } = renderHook(() => useConversationList());
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    act(() => {
      result.current.applyConversationUpdate("does-not-exist", { title: "Ghost", icon: "general" });
    });

    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.conversations[0]?.title).toBe("Argentina defence");
  });
});
