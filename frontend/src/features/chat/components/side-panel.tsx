"use client";

import { useEffect, useState, type ReactNode, type TransitionEvent } from "react";
import { PanelLeftClose } from "lucide-react";

import { useMediaQuery } from "@/hooks/use-media-query";
import { PanelCompare } from "@/features/chat/components/panel-compare";
import { PanelMatch } from "@/features/chat/components/panel-match";
import { PanelPlayer } from "@/features/chat/components/panel-player";
import { PanelRanking } from "@/features/chat/components/panel-ranking";
import { PanelTeam } from "@/features/chat/components/panel-team";
import type {
  EntityRef,
  MatchSummary,
  PanelState,
  PlayerComparison,
  PlayerRanking,
  PlayerSummary,
  TeamSummary,
} from "@/features/chat/types";

const DESKTOP_BREAKPOINT = "(min-width: 768px)";
const PANEL_CONTENT_WIDTH = "w-[480px]";
const PANEL_OPEN_WIDTH = "w-[calc(3rem+480px)]";
const PANEL_ENTER_MS = 300;

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
    case "ranking":
      return (
        <PanelRanking
          ranking={data as PlayerRanking}
          isSheet={isSheet}
          fromMessage={fromMessage}
          {...handlers}
        />
      );
    default:
      return null;
  }
}

function PanelToggle({
  collapsed,
  onCollapse,
  onExpand,
}: {
  collapsed: boolean;
  onCollapse: () => void;
  onExpand: () => void;
}) {
  return (
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
  );
}

/**
 * The first open grows the shell from the right edge. The full drawer stays
 * pinned to that edge, so it slides into place instead of popping in. Once
 * the slide finishes, later collapse only clips the content and leaves the rail.
 */
function DesktopDrawer({
  entered,
  settled,
  collapsed,
  onCollapse,
  onExpand,
  onSettled,
  children,
}: {
  entered: boolean;
  settled: boolean;
  collapsed: boolean;
  onCollapse: () => void;
  onExpand: () => void;
  onSettled: () => void;
  children: ReactNode;
}) {
  const revealFromRight = !settled && !collapsed;
  const shellWidth = revealFromRight
    ? entered
      ? PANEL_OPEN_WIDTH
      : "w-0"
    : collapsed
      ? "w-12"
      : PANEL_OPEN_WIDTH;

  function handleTransitionEnd(event: TransitionEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget || event.propertyName !== "width") return;
    if (revealFromRight && entered) onSettled();
  }

  return (
    <div
      onTransitionEnd={handleTransitionEnd}
      className={`flex h-full shrink-0 overflow-hidden border-l border-border-strong bg-surface-900 transition-[width] duration-300 ease-in-out motion-reduce:transition-none ${
        revealFromRight ? "justify-end" : "justify-start"
      } ${shellWidth}`}
    >
      <div className={`flex h-full shrink-0 ${PANEL_OPEN_WIDTH}`}>
        <PanelToggle collapsed={collapsed} onCollapse={onCollapse} onExpand={onExpand} />
        <div className={`h-full overflow-y-auto ${PANEL_CONTENT_WIDTH}`}>{children}</div>
      </div>
    </div>
  );
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
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const { openEntity, collapsed } = panelState;
  const data = openEntity ? resolveEntity(openEntity) : null;
  const isOpen = Boolean(openEntity && data);
  const [entered, setEntered] = useState(false);
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    if (!isOpen || !isDesktop || reduceMotion) {
      setEntered(false);
      setSettled(false);
      return;
    }
    const frame = requestAnimationFrame(() => setEntered(true));
    const timer = window.setTimeout(() => setSettled(true), PANEL_ENTER_MS + 80);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [isOpen, isDesktop, reduceMotion]);

  if (!openEntity || !data) return null;

  if (isDesktop) {
    return (
      <DesktopDrawer
        entered={entered}
        settled={settled || reduceMotion}
        collapsed={collapsed}
        onCollapse={onCollapse}
        onExpand={onExpand}
        onSettled={() => setSettled(true)}
      >
        {renderPanelBody(
          openEntity,
          data,
          fromMessagePreview,
          { onClose, onJumpToMessage },
          false,
        )}
      </DesktopDrawer>
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
