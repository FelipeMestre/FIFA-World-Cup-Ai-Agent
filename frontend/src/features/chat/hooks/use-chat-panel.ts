"use client";

import { useCallback, useState } from "react";

import type { EntityRef, PanelState } from "@/features/chat/types";

const INITIAL_STATE: PanelState = {
  openEntity: null,
  collapsed: false,
  sourceMessageId: null,
};

/**
 * The side-panel state machine from design/README.md's "Panel behavior":
 * one entity at a time (opening another replaces it), stays open across
 * follow-up turns, collapse keeps the last entity one click away, close
 * clears it entirely.
 */
export function useChatPanel() {
  const [state, setState] = useState<PanelState>(INITIAL_STATE);

  const openEntity = useCallback((ref: EntityRef, sourceMessageId: string) => {
    setState((prev) => {
      const showingThisEntity =
        prev.openEntity?.type === ref.type && prev.openEntity.id === ref.id && !prev.collapsed;
      if (showingThisEntity) return { ...prev, collapsed: true };
      return { openEntity: ref, collapsed: false, sourceMessageId };
    });
  }, []);

  const collapse = useCallback(() => {
    setState((prev) => ({ ...prev, collapsed: true }));
  }, []);

  const expand = useCallback(() => {
    setState((prev) => ({ ...prev, collapsed: false }));
  }, []);

  const close = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  const jumpToMessage = useCallback(() => {
    if (!state.sourceMessageId) return;
    document.getElementById(state.sourceMessageId)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, [state.sourceMessageId]);

  return { state, openEntity, collapse, expand, close, jumpToMessage };
}
