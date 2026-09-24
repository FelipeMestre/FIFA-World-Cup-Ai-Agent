"use client";

import { ListOrdered } from "lucide-react";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { positionLabel } from "@/features/chat/components/profile-tag";
import { WidgetFrame } from "@/features/chat/components/widget-frame";
import type { PlayerRanking } from "@/features/chat/types";

/** Compact ranked list. Open the side panel for per-player stats. */
export function WidgetRanking({
  ranking,
  active,
  onViewDetails,
}: {
  ranking: PlayerRanking;
  active: boolean;
  onViewDetails: () => void;
}) {
  const maxValue = Math.max(1, ...ranking.rows.map((row) => Math.abs(row.sortValue)));
  const previewRows = ranking.rows.slice(0, 8);

  return (
    <WidgetFrame
      ariaLabel={`Player ranking: ${ranking.rankByLabel}`}
      icon={<ListOrdered className="size-4" aria-hidden />}
      label="Player ranking"
      scopeText={ranking.scopeLabel}
      footerCaption={ranking.footerCaption}
      active={active}
      onViewDetails={onViewDetails}
    >
      <div className="flex shrink-0 items-baseline justify-between gap-ds-3 px-ds-4 pt-ds-4 pb-ds-2">
        <span className="text-heading-md">{ranking.rankByLabel}</span>
        <span className="text-label-sm text-ink-muted">
          {ranking.scope === "world_cup" ? "World Cup" : "Club seasons"}
        </span>
      </div>
      <ol className="flex flex-col gap-ds-3 px-ds-4 pb-ds-4">
        {previewRows.map((row) => (
          <li key={row.playerId} className="flex items-center gap-ds-3">
            <span className="w-6 shrink-0 font-mono text-data-sm text-ink-muted">
              {row.rank}
            </span>
            <AvatarBadge label={row.initials} size={32} className="text-label-sm" />
            <div className="flex min-w-0 grow flex-col gap-0.5">
              <div className="flex items-baseline justify-between gap-ds-2">
                <span className="truncate text-body-md text-ink-primary">{row.name}</span>
                <span className="shrink-0 font-mono text-data-lg text-ink-primary">
                  {row.value}
                </span>
              </div>
              <span className="text-label-sm text-ink-muted">
                {row.teamCode} · {positionLabel(row.position)}
              </span>
              <div className="h-1 overflow-hidden rounded-full bg-surface-700">
                <div
                  className="h-full rounded-full bg-accent-live"
                  style={{
                    width: `${Math.round((Math.abs(row.sortValue) / maxValue) * 100)}%`,
                  }}
                />
              </div>
            </div>
          </li>
        ))}
      </ol>
    </WidgetFrame>
  );
}
