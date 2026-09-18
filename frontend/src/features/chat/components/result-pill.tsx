import { cn } from "@/lib/utils";
import type { ResultLetter } from "@/features/chat/types";

const RESULT_COLOR: Record<ResultLetter, string> = {
  W: "border-data-positive text-data-positive",
  D: "border-data-neutral text-data-neutral",
  L: "border-data-negative text-data-negative",
};

/**
 * W/D/L result pill. The letter itself is the glyph -- design/README.md's
 * "outcome colors never appear without a glyph" rule, satisfied by the
 * letter carrying the meaning, color only reinforcing it.
 */
export function ResultPill({
  result,
  className,
}: {
  result: ResultLetter;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "flex size-6 items-center justify-center rounded-sm border font-mono text-data-sm font-semibold",
        RESULT_COLOR[result],
        className,
      )}
    >
      {result}
    </span>
  );
}
