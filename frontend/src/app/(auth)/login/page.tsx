import { LoginForm } from "@/features/auth";

/** Thin routing shell -- composes the auth feature's login form (Login.dc.html). */
export default function LoginPage() {
  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-surface-950 p-6">
      <svg
        className="pointer-events-none absolute inset-0 hidden md:block"
        width="1440"
        height="900"
        viewBox="0 0 1440 900"
        fill="none"
        stroke="var(--color-surface-800)"
        strokeWidth="2"
        aria-hidden="true"
        preserveAspectRatio="xMidYMid slice"
      >
        <path d="M720 0v900" />
        <circle cx="720" cy="450" r="150" />
        <circle cx="720" cy="450" r="4" fill="var(--color-surface-800)" />
        <rect x="-2" y="230" width="220" height="440" />
        <rect x="1222" y="230" width="220" height="440" />
      </svg>
      <LoginForm />
    </main>
  );
}
