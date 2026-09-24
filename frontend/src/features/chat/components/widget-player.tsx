"use client";

import { User } from "lucide-react";

import { AvatarBadge } from "@/components/shared/avatar-badge";
import { PlayerClubProfileFacts } from "@/features/chat/components/player-club-profile";
import {
  DisciplineTag,
  positionLabel,
  PositionTag,
  TierTag,
} from "@/features/chat/components/profile-tag";
import { StatChip } from "@/features/chat/components/stat-chip";
import { WidgetFrame } from "@/features/chat/components/widget-frame";
import type { PlayerSummary } from "@/features/chat/types";

/** Player analysis widget (design/artboards/WidgetPlayer.dc.html). */
export function WidgetPlayer({
  player,
  active,
  onViewDetails,
}: {
  player: PlayerSummary;
  active: boolean;
  onViewDetails: () => void;
}) {
  return (
    <WidgetFrame
      ariaLabel={`Player analysis: ${player.name}`}
      icon={<User className="size-4" aria-hidden />}
      label="Player analysis"
      scopeText={player.scopeLabel}
      footerCaption={player.footerCaption}
      active={active}
      onViewDetails={onViewDetails}
    >
      <div className="flex shrink-0 items-center gap-3.5 px-4 pt-4 pb-3">
        <AvatarBadge label={player.initials} size={56} className="text-heading-md" />
        <div className="flex min-w-0 grow flex-col gap-0.5">
          <span className="text-heading-lg">{player.name}</span>
          <span className="text-body-sm text-ink-secondary">
            {player.teamCode} · {positionLabel(player.position)}
          </span>
        </div>
      </div>

      <div className="flex shrink-0 flex-col gap-1.5 px-4 pb-3.5">
        <span className="text-label-sm text-ink-muted">Stats-derived profile</span>
        <div className="flex flex-wrap gap-1.5">
          <PositionTag position={player.position} />
          <TierTag label={player.tierLabel} filled={player.tierSegments} />
          <DisciplineTag label={player.disciplineLabel} />
        </div>
      </div>

      {player.clubProfile ? (
        <PlayerClubProfileFacts profile={player.clubProfile} layout="widget" />
      ) : null}

      <div className="grid grow grid-cols-2 content-start gap-2 px-4 pb-4 sm:grid-cols-4">
        {player.chips.map((chip) => (
          <StatChip key={chip.label} label={chip.label} value={chip.value} />
        ))}
      </div>
    </WidgetFrame>
  );
}
