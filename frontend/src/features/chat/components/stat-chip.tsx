import { cn } from "@/lib/utils";

/**
 * Stat chip/tile atom (Components.dc.html "Stat chip and tile"). "chip" is a
 * recessed surface-900 well used inside an 800 widget body; "tile" is a
 * raised surface-800 card used inside a 900 panel body -- same label/value
 * styling either way.
 */
export function StatChip({
  label,
  value,
  valueClassName,
  variant = "chip",
  secondary,
  className,
}: {
  label: string;
  value: string;
  valueClassName?: string;
  variant?: "chip" | "tile";
  secondary?: { fieldLabel: string; delta: string };
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-ds-1 border",
        variant === "chip"
          ? "rounded-sm border-border-subtle bg-surface-900 px-ds-3 py-ds-2"
          : "rounded-lg border-border-strong bg-surface-800 px-[14px] py-ds-3",
        className,
      )}
    >
      <span className="text-label-sm text-ink-muted">{label}</span>
      <span className={cn("text-data-lg text-ink-primary", valueClassName)}>
        {value}
      </span>
      {secondary ? (
        <span className="flex items-center justify-between gap-ds-2 text-body-sm">
          <span className="text-ink-muted">Field {secondary.fieldLabel}</span>
          <span className="font-mono text-data-sm text-data-neutral">
            {secondary.delta}
          </span>
        </span>
      ) : null}
    </div>
  );
}
