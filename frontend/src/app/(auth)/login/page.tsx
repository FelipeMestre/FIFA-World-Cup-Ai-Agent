import { AssistantMark } from "@/components/shared/assistant-mark";
import { LoginForm } from "@/features/auth";

// @next-codemod-ignore Cache Components adoption: this segment temporarily allows blocking.
// Remove this opt-out after verifying the segment passes validation without it.
// See: https://nextjs.org/docs/app/guides/migrating-to-cache-components
export const instant = false;

/**
 * Thin routing shell -- composes the auth feature's login form (Login.dc.html).
 * The greeting and the data footnote sit outside the card in the design, and
 * are static, so they stay on the server side of the boundary.
 */
export default function LoginPage() {
  return (
    <main className="relative flex min-h-dvh flex-col items-center justify-center gap-7 overflow-hidden bg-surface-950 p-6">
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(640px 420px at 50% 30%, rgba(126,111,238,0.22), rgba(126,111,238,0) 70%), radial-gradient(520px 380px at 85% 95%, rgba(78,142,247,0.12), rgba(78,142,247,0) 70%)",
        }}
      />
      <svg
        className="pointer-events-none absolute inset-0 size-full"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
        stroke="#F4F6F9"
        strokeOpacity="0.04"
        strokeWidth="1.5"
        aria-hidden="true"
      >
        <path d="M720 0v900" />
        <circle cx="720" cy="450" r="160" />
        <rect x="-2" y="220" width="240" height="460" />
        <rect x="1202" y="220" width="240" height="460" />
        <rect x="-2" y="340" width="90" height="220" />
        <rect x="1352" y="340" width="90" height="220" />
      </svg>

      <div className="relative flex flex-col items-center gap-3.5 text-center">
        <AssistantMark
          size={64}
          radius="rounded-[18px]"
          className="shadow-[0_0_0_1px_rgba(78,142,247,0.4),0_16px_40px_rgba(78,142,247,0.35)]"
        />
        <h1 className="text-display-md font-bold tracking-[-0.02em]">Welcome back</h1>
        <p className="max-w-[360px] text-[15px] leading-[22px] text-ink-secondary">
          Sign in to World Cup AI Scout, your 2026 tournament analyst.
        </p>
      </div>

      <LoginForm />

      <span className="relative text-center text-[12px] leading-4 text-ink-muted">
        Answers built on official tournament match data · 104 matches · 48 teams
      </span>
    </main>
  );
}
