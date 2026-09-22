"use client";

import { PanelLeftClose } from "lucide-react";

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
  handlers: {
    onClose: () => void;
    onJumpToMessage: () => void;
  },
  isSheet: boolean,
) {
  switch (entity.type) {
    case "team":
      return (
        <PanelTeam
          team={data as TeamSummary}
          isSheet={isSheet}
          fromMessage={fromMessage}
          {...handlers}
        />
      );
    case "match":
      return (
        <PanelMatch
          match={data as MatchSummary}
          isSheet={isSheet}
          fromMessage={fromMessage}
          {...handlers}
        />
      );
    case "player":
      return (
        <PanelPlayer
          player={data as PlayerSummary}
          isSheet={isSheet}
          fromMessage={fromMessage}
          {...handlers}
        />
      );
    case "compare":
      return (
        <PanelCompare
          comparison={data as PlayerComparison}
          isSheet={isSheet}
          fromMessage={fromMessage}
          {...handlers}
        />
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
 *
 * On desktop the toggle lives on a persistent left rail (`w-12`, always
 * mounted) instead of inside the panel's own header: the header is a
 * different DOM subtree that unmounts/remounts across collapsed <-> expanded
 * (its content depends on `openEntity`'s data), so a button living there
 * can't smoothly animate across that swap -- same button, same position,
 * same size in both states, just spins in place via `rotate-180`.
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
    return (
      <div className="flex shrink-0 border-l border-border-strong bg-surface-900">
        <div className="flex w-12 shrink-0 flex-col items-center border-r border-border-subtle pt-1">
          <button
            type="button"
            onClick={collapsed ? onExpand : onCollapse}
            aria-label={collapsed ? "Expand panel" : "Collapse panel"}
            className="focus-ring flex size-11 items-center justify-center rounded-md text-ink-secondary hover:bg-surface-800"
          >
            <PanelLeftClose
              className={`size-5 transition-transform duration-300 ease-in-out ${
                collapsed ? "rotate-180" : ""
              }`}
              aria-hidden
            />
          </button>
        </div>
        {/* Fixed-width inner content clipped by the outer's overflow-hidden
            as its width animates -- a slide/wipe reveal instead of the
            content itself squishing during the transition. */}
        <div
          className={`overflow-hidden transition-[width] duration-300 ease-in-out ${
            collapsed ? "w-0" : "w-[433px]"
          }`}
        >
          <div className="h-full w-[433px] overflow-y-auto">
            {renderPanelBody(
              openEntity,
              data,
              fromMessagePreview,
              { onClose, onJumpToMessage },
              false,
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-40">
      <div
        className="absolute inset-0 bg-overlay-scrim"
        onClick={onClose}
        aria-hidden
      />
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
          {renderPanelBody(
            openEntity,
            data,
            fromMessagePreview,
            { onClose, onJumpToMessage },
            true,
          )}
        </div>
      </div>
    </div>
  );
}
