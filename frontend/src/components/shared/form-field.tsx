import type { ComponentProps, ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * Label + Input (+ error) wrapper. The one @layer components-worthy pattern
 * reused across 2+ forms (per AGENTS.md's Tailwind rules) -- kept as a real
 * component rather than a CSS class since it composes multiple elements.
 */
export function FormField({
  id,
  label,
  labelExtra,
  error,
  className,
  ...inputProps
}: ComponentProps<typeof Input> & {
  id: string;
  label: string;
  labelExtra?: ReactNode;
  error?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <Label htmlFor={id} className="text-label-md text-ink-secondary">
          {label}
        </Label>
        {labelExtra}
      </div>
      <Input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={cn(
          "h-11 border-border-strong bg-surface-700 px-3 text-body-md text-ink-primary placeholder:text-ink-muted focus-visible:border-accent-live focus-visible:ring-accent-live/50",
          className,
        )}
        {...inputProps}
      />
      {error ? (
        <p id={`${id}-error`} className="text-body-sm text-data-negative">
          {error}
        </p>
      ) : null}
    </div>
  );
}
