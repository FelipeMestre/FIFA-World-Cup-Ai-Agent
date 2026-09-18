import { cn } from "@/lib/utils";

/**
 * The Owl Analytics assistant mark (owl SVG on a white roundel). Used in the
 * app header, chat bubbles and the login page -- brand violet is reserved
 * for exactly this and the page's one primary action, per design/README.md.
 */
export function AssistantMark({
  size = 32,
  radius = "rounded-lg",
  className,
}: {
  size?: number;
  radius?: string;
  className?: string;
}) {
  const iconSize = Math.round(size * 0.875);
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center bg-white shadow-sm",
        radius,
        className,
      )}
      style={{ width: size, height: size }}
    >
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 32 32"
        aria-hidden="true"
      >
        <path
          fill="#7E6FEE"
          d="M8.5 4.5L12 9.2Q16 8 20 9.2L23.5 4.5L24.6 12Q27.2 15.6 26.6 20.4Q25.8 26.6 16 27.6Q6.2 26.6 5.4 20.4Q4.8 15.6 7.4 12Z"
        />
        <path
          fill="none"
          stroke="#0D0630"
          strokeOpacity="0.4"
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M7.6 19Q8.6 24.4 13 26.4M24.4 19Q23.4 24.4 19 26.4M13.6 22.6l1.2 1 1.2-1 1.2 1 1.2-1"
        />
        <circle cx="12.2" cy="14.6" r="3.9" fill="#FFFFFF" stroke="#0D0630" strokeWidth="1.1" />
        <circle cx="19.8" cy="14.6" r="3.9" fill="#FFFFFF" stroke="#0D0630" strokeWidth="1.1" />
        <circle cx="12.2" cy="14.6" r="1.9" fill="#0D0630" />
        <circle cx="19.8" cy="14.6" r="1.9" fill="#0D0630" />
        <circle cx="12.9" cy="13.9" r="0.6" fill="#FFFFFF" />
        <circle cx="20.5" cy="13.9" r="0.6" fill="#FFFFFF" />
        <path fill="#0D0630" d="M16 18.4L14.9 19.9L16 21.4L17.1 19.9Z" />
        <path
          fill="none"
          stroke="#0D0630"
          strokeWidth="1.5"
          strokeLinecap="round"
          d="M8.5 29.3H23.5M13 27.3v1.8M14.6 27.3v1.8M17.4 27.3v1.8M19 27.3v1.8"
        />
      </svg>
    </div>
  );
}
