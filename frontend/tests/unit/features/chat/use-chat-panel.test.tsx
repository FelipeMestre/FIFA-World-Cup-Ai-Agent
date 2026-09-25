import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useChatPanel } from "@/features/chat/hooks/use-chat-panel";
import type { EntityRef } from "@/features/chat/types";

const team: EntityRef = { type: "team_compare", id: "1-vs-2" };

describe("useChatPanel", () => {
  it("opens the side panel, then collapses it when the same entity is opened again", () => {
    const { result } = renderHook(() => useChatPanel());

    act(() => result.current.openEntity(team, "message-1"));
    expect(result.current.state.openEntity).toEqual(team);
    expect(result.current.state.collapsed).toBe(false);

    act(() => result.current.openEntity(team, "message-1"));
    expect(result.current.state.openEntity).toEqual(team);
    expect(result.current.state.collapsed).toBe(true);
  });

  it("reopens a collapsed panel instead of clearing it", () => {
    const { result } = renderHook(() => useChatPanel());

    act(() => result.current.openEntity(team, "message-1"));
    act(() => result.current.collapse());
    act(() => result.current.openEntity(team, "message-1"));

    expect(result.current.state.openEntity).toEqual(team);
    expect(result.current.state.collapsed).toBe(false);
  });
});
