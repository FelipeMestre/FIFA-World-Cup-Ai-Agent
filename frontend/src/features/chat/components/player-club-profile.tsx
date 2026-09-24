import { clubProfileFacts } from "@/features/chat/components/player-club-format";
import type { PlayerClubProfile } from "@/features/chat/types";

/** Transfermarkt profile facts. Renders nothing when every field is empty. */
export function PlayerClubProfileFacts({
  profile,
  layout,
}: {
  profile: PlayerClubProfile;
  layout: "widget" | "panel";
}) {
  const facts = clubProfileFacts(profile);
  if (facts.length === 0) {
    return null;
  }

  const heading =
    layout === "panel" ? (
      <h3 className="text-heading-sm">Club profile</h3>
    ) : (
      <span className="text-label-sm text-ink-muted">Club profile</span>
    );

  return (
    <div
      className={
        layout === "widget"
          ? "flex flex-col gap-2 px-4 pb-3.5"
          : "flex shrink-0 flex-col gap-3 border-b border-border-subtle p-5"
      }
    >
      {heading}
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
        {facts.map((fact) => (
          <div key={fact.label} className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-label-sm text-ink-muted">{fact.label}</dt>
            <dd className="truncate text-body-sm text-ink-primary">{fact.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
