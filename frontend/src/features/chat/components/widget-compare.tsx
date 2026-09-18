"use client";

import { BarChart3 } from "lucide-react";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { DivergingBarRow } from "@/features/chat/components/comparison-row";
import { WidgetFrame } from "@/features/chat/components/widget-frame";
import type { PlayerComparison } from "@/features/chat/types";

/** Player comparison widget (design/artboards/WidgetCompare.dc.html). */
export function WidgetCompare({
  comparison,
  active,
  onViewDetails,
}: {
  comparison: PlayerComparison;
  active: boolean;
  onViewDetails: () => void;
}) {
  const { playerA, playerB } = comparison;
  // The compact widget shows only its 4 headline rows; the full panel (via
  // "View full details") shows every row in comparison.rows.
  const headlineOrder = ["Assists", "Shots", "Goals + assists", "Goals"];
  const headlineRows = headlineOrder
    .map((label) => comparison.rows.find((row) => row.label === label))
    .filter((row): row is (typeof comparison.rows)[number] => row != null);

  return (
    <WidgetFrame
      ariaLabel={`Player comparison: ${playerA.name} and ${playerB.name}`}
      icon={<BarChart3 className="size-4" aria-hidden />}
      label="Player comparison"
      scopeText={comparison.scopeLabel}
      footerCaption={comparison.minMinutesCaption}
      active={active}
      onViewDetails={onViewDetails}
    >
      <div className="grid shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-3 border-b border-border-subtle p-4">
        <div className="flex flex-col items-start gap-1">
          <AvatarBadge label={playerA.initials} size={40} seriesColor="var(--color-accent-live)" />
          <span className="text-heading-md">{playerA.name}</span>
          <span className="text-body-sm text-ink-secondary">
            {playerA.teamCode} · {playerA.position} · {playerA.minutes} min
          </span>
        </div>
        <span className="text-label-sm text-ink-muted">vs</span>
        <div className="flex flex-col items-end gap-1 text-right">
          <AvatarBadge label={playerB.initials} size={40} seriesColor="var(--color-ink-secondary)" />
          <span className="text-heading-md">{playerB.name}</span>
          <span className="text-body-sm text-ink-secondary">
            {playerB.teamCode} · {playerB.position} · {playerB.minutes} min
          </span>
        </div>
      </div>

      <div className="flex grow flex-col gap-3.5 px-4 pt-3.5 pb-4">
        <span className="text-label-sm text-ink-muted">Where they differ most</span>
        {headlineRows.map((row) => {
          const aNum = Number(row.playerAValue);
          const bNum = Number(row.playerBValue);
          const max = Math.max(aNum, bNum) || 1;
          const aLeads = row.playerAIsBetter;
          const leaderName = aLeads ? playerA.name : playerB.name;
          const delta = Math.abs(aNum - bNum).toFixed(2);
          return (
            <DivergingBarRow
              key={row.label}
              label={row.label}
              leaderCaption={`▲ +${delta} ${leaderName}`}
              leaderColorClass={aLeads ? "text-accent-live" : "text-ink-secondary"}
              aValue={row.playerAValue}
              bValue={row.playerBValue}
              aPct={Math.round((aNum / max) * 100)}
              bPct={Math.round((bNum / max) * 100)}
              aInkClass={aLeads ? "text-ink-primary" : "text-ink-secondary"}
              bInkClass={!aLeads ? "text-ink-primary" : "text-ink-secondary"}
            />
          );
        })}
        <div className="mt-0.5 flex flex-col gap-1.5 border-t border-border-subtle pt-3 text-body-sm text-ink-secondary">
          {comparison.insights.map((insight, i) => (
            <span key={insight} className="flex items-start gap-2">
              <span
                className={`mt-1.5 size-2 shrink-0 rounded-[2px] ${i === 0 ? "bg-accent-live" : "bg-ink-secondary"}`}
              />
              {insight}
            </span>
          ))}
        </div>
      </div>
    </WidgetFrame>
  );
}
