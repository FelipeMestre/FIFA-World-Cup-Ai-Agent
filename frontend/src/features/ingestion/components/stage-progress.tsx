import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/features/ingestion/types";

const STAGE_LABEL: Record<string, string> = {
  national_teams: "National teams",
  clubs: "Clubs",
  players: "Players",
  player_valuations: "Player valuations",
  transfers: "Transfers",
  game_lineups: "Game lineups",
  game_events: "Game events",
  club_games: "Club games",
  real_player_season_stat: "Season stats",
};

function stageLabel(stage: string): string {
  return STAGE_LABEL[stage] ?? stage;
}

/** Renders every pipeline stage in order, marking each one done, current, or
 * still ahead -- `job.allStages` is the source of order/membership so this
 * never drifts from what the backend's pipeline actually runs.
 */
export function StageProgress({ job }: { job: JobStatus }) {
  if (job.allStages.length === 0) {
    return null;
  }
  const completedStages = new Set(job.stageCheckpoints.map((checkpoint) => checkpoint.stage));
  const completedCount = job.allStages.filter((stage) => completedStages.has(stage)).length;

  return (
    <div className="flex flex-col gap-ds-2">
      <span className="text-label-sm text-ink-muted">
        Stage {completedCount} of {job.allStages.length}
        {job.currentStage ? ` -- last completed: ${stageLabel(job.currentStage)}` : ""}
      </span>
      <div className="flex flex-wrap gap-ds-2">
        {job.allStages.map((stage) => {
          const isDone = completedStages.has(stage);
          const isCurrent = stage === job.currentStage;
          return (
            <Badge
              key={stage}
              variant={isDone ? "default" : "outline"}
              className={isCurrent ? "border-accent-live" : undefined}
            >
              {stageLabel(stage)}
            </Badge>
          );
        })}
      </div>
    </div>
  );
}
