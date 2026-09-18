import { cn } from "@/lib/utils";

/**
 * Circular initials avatar for a team code or player initials. An optional
 * 2px `seriesColor` ring marks side A/home/player A (accent-live) vs side
 * B/away/player B (ink-secondary), per design/README.md's series mapping --
 * never any other pairing.
 */
export function AvatarBadge({
  label,
  size = 44,
  seriesColor,
  className,
}: {
  label: string;
  size?: number;
  seriesColor?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-surface-700 font-display font-semibold text-ink-primary",
        className,
      )}
      style={{
        width: size,
        height: size,
        fontSize: Math.max(11, Math.round(size * 0.3)),
        border: `${seriesColor ? 2 : 1}px solid ${seriesColor ?? "var(--color-border-strong)"}`,
      }}
    >
      {label}
    </div>
  );
}
