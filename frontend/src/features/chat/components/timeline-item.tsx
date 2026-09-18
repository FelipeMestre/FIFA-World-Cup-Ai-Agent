import { ArrowLeftRight, Circle, RectangleVertical, ScanLine } from "lucide-react";

import { cn } from "@/lib/utils";
import type { MatchEvent } from "@/features/chat/types";

const EVENT_ICON: Record<MatchEvent["kind"], typeof Circle> = {
  goal: Circle,
  card: RectangleVertical,
  var: ScanLine,
  sub: ArrowLeftRight,
};

const EVENT_LABEL: Record<MatchEvent["kind"], string> = {
  goal: "Goal",
  card: "Card",
  var: "VAR review",
  sub: "Substitution",
};

/**
 * One event on the match timeline spine: minute, icon node, title/detail,
 * team-code chip. Shared by the compact WidgetMatch events list and the
 * full PanelMatch timeline.
 */
export function TimelineItem({
  event,
  seriesColorClass,
  showConnector = true,
}: {
  event: MatchEvent;
  /** Tailwind background class for the team-code marker, e.g. "bg-accent-live". */
  seriesColorClass: string;
  showConnector?: boolean;
}) {
  const Icon = EVENT_ICON[event.kind];
  const isGoal = event.kind === "goal";

  return (
    <li className="grid min-h-14 grid-cols-[44px_28px_1fr_auto] gap-x-3">
      <span className="pt-1.5 text-right font-mono text-data-sm text-ink-muted">
        {event.minute}
      </span>
      <div className="flex flex-col items-center">
        <span
          className={cn(
            "flex size-7 items-center justify-center rounded-full border border-border-strong bg-surface-800",
            isGoal ? "text-ink-primary" : "text-ink-secondary",
          )}
        >
          <Icon className="size-3.5" aria-label={EVENT_LABEL[event.kind]} />
        </span>
        {showConnector ? <span className="min-h-3 w-px grow bg-border-subtle" /> : null}
      </div>
      <div className="flex flex-col gap-0.5 py-1 pb-3">
        <span className="text-body-md font-medium text-ink-primary">{event.title}</span>
        {event.kind === "sub" ? (
          <span className="flex flex-wrap gap-x-3 gap-y-0.5 text-body-sm text-ink-secondary">
            <span>
              <span className="text-data-positive">▲ On</span> {event.subOn}
            </span>
            <span>
              <span className="text-data-negative">▼ Off</span> {event.subOff}
            </span>
          </span>
        ) : (
          <span className="text-body-sm text-ink-secondary">{event.detail}</span>
        )}
      </div>
      <span className="flex items-start gap-1 pt-1.5 font-mono text-data-sm text-ink-muted">
        <span className={cn("mt-1 size-2 rounded-[2px]", seriesColorClass)} />
        {event.teamCode}
      </span>
    </li>
  );
}
