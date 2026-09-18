"use client";

import { PanelRightOpen } from "lucide-react";

import { useMediaQuery } from "@/hooks/use-media-query";
import { PanelCompare } from "@/features/chat/components/panel-compare";
import { PanelMatch } from "@/features/chat/components/panel-match";
import { PanelPlayer } from "@/features/chat/components/panel-player";
import { PanelTeam } from "@/features/chat/components/panel-team";
import type {
  EntityRef,
  MatchSummary,
  PanelState,
  PlayerComparison,
  PlayerSummary,
  TeamSummary,
} from "@/features/chat/types";

const DESKTOP_BREAKPOINT = "(min-width: 768px)";

function renderPanelBody(
  entity: EntityRef,
  data: unknown,
  fromMessage: string,
  handlers: { onCollapse?: () => void; onClose: () => void; onJumpToMessage: () => void },
  isSheet: boolean,
) {
  switch (entity.type) {
    case "team":
      return <PanelTeam team={data as TeamSummary} isSheet={isSheet} fromMessage={fromMessage} {...handlers} />;
    case "match":
      return <PanelMatch match={data as MatchSummary} isSheet={isSheet} fromMessage={fromMessage} {...handlers} />;
    case "player":
      return <PanelPlayer player={data as PlayerSummary} isSheet={isSheet} fromMessage={fromMessage} {...handlers} />;
    case "compare":
      return (
        <PanelCompare comparison={data as PlayerComparison} isSheet={isSheet} fromMessage={fromMessage} {...handlers} />
      );
    default:
      return null;
  }
}

/**
 * The desktop drawer / mobile sheet container implementing design/README.md's
 * panel state machine: one entity at a time, stays open across turns,
 * collapse keeps it one click away, close clears it. Mobile has no collapse
 * control -- it's a full-height sheet over a scrim instead.
 */
export function SidePanel({
  panelState,
  resolveEntity,
  fromMessagePreview,
  onCollapse,
  onExpand,
  onClose,
  onJumpToMessage,
}: {
  panelState: PanelState;
  resolveEntity: (ref: EntityRef) => unknown;
  fromMessagePreview: string;
  onCollapse: () => void;
  onExpand: () => void;
  onClose: () => void;
  onJumpToMessage: () => void;
}) {
  const isDesktop = useMediaQuery(DESKTOP_BREAKPOINT);
  const { openEntity, collapsed } = panelState;

  if (!openEntity) return null;
  const data = resolveEntity(openEntity);
  if (!data) return null;

  if (isDesktop) {
    if (collapsed) {
      return (
        <button
          type="button"
          onClick={onExpand}
          aria-label="Expand panel"
          className="focus-ring fixed top-1/2 right-0 flex h-16 w-8 -translate-y-1/2 items-center justify-center rounded-l-md border border-r-0 border-border-strong bg-surface-800 text-ink-secondary hover:bg-surface-700"
        >
          <PanelRightOpen className="size-4" aria-hidden />
        </button>
      );
    }
    return (
      <div className="w-[481px] shrink-0 overflow-y-auto border-l border-border-strong bg-surface-900">
        {renderPanelBody(
          openEntity,
          data,
          fromMessagePreview,
          { onCollapse, onClose, onJumpToMessage },
          false,
        )}
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-overlay-scrim" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Detail sheet"
        className="absolute inset-x-0 top-10 bottom-0 flex flex-col overflow-hidden rounded-t-xl border-t border-border-strong bg-surface-900 shadow-md"
      >
        <div className="flex h-5 shrink-0 items-center justify-center">
          <span className="h-1 w-9 rounded-full bg-border-strong" />
        </div>
        <div className="min-h-0 grow overflow-y-auto">
          {renderPanelBody(openEntity, data, fromMessagePreview, { onClose, onJumpToMessage }, true)}
        </div>
      </div>
    </div>
  );
}
