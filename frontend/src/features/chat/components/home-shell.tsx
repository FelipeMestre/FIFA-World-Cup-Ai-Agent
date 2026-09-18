"use client";

import { useRouter } from "next/navigation";

import { AppHeader } from "@/components/layout/app-header";
import { AssistantMark } from "@/components/shared/assistant-mark";
import { HomePromptCard } from "@/features/chat/components/home-prompt-card";

/**
 * Home page shell (HomeActive.dc.html) — the empty/hero state before any chat starts.
 * Composes: AppHeader, hero with AssistantMark + headline + description, Composer,
 * and a 2x2 grid of suggested prompt cards. No auth required.
 */
export function HomeShell() {
  const router = useRouter();

  // Suggested prompts matching HomeActive.dc.html exactly
  const suggestedPrompts = [
    {
      title: "Compare Messi vs Mbappé",
      hint: "Player comparison · per 90",
      iconPath: "M5 16V9M10 16V4M15 16v-5",
      tintClass: "bg-brand/16",
      inkColor: "#998DF2",
    },
    {
      title: "How did Argentina perform defensively?",
      hint: "Team analysis · 7 matches",
      iconPath: "M10 3l6 2.5V10c0 3.5-2.6 6-6 7-3.4-1-6-3.5-6-7V5.5z",
      tintClass: "bg-accent-live/14",
      inkColor: "#4E8EF7",
    },
    {
      title: "France vs Spain semifinal breakdown",
      hint: "Match analysis · events and lineups",
      iconPath: "M3 5h14v10H3zM10 5v10",
      tintClass: "bg-data-positive/12",
      inkColor: "#35D18E",
    },
    {
      title: "Which keeper made the most saves?",
      hint: "Player ranking · goalkeepers",
      iconPath: "M10 4a3 3 0 1 1 0 6 3 3 0 0 1 0-6M4.5 16.5c0.8-3 3-4.5 5.5-4.5s4.7 1.5 5.5 4.5",
      tintClass: "bg-ink-muted/12",
      inkColor: "#ABB4C4",
    },
  ];

  const handlePromptClick = (label: string) => {
    router.push(`/?prompt=${encodeURIComponent(label)}`);
  };

  return (
    <div className="flex h-dvh flex-col bg-surface-950">
      <AppHeader />
      <div className="flex min-h-0 grow">
        {/* Sidebar placeholder - using the same width as expanded AppSidebar (264px) */}
        <aside
          className="hidden shrink-0 w-[264px] border-r border-border-subtle bg-surface-900 md:block"
          aria-label="Conversations"
        >
          <div className="flex h-full flex-col">
            <div className="flex flex-col gap-5 p-5 pt-6">
              <div className="flex items-center gap-2.5 px-1.5">
                <AssistantMark size={32} radius="rounded-xl" />
                <div className="flex flex-col">
                  <span className="text-heading-md">World Cup AI Scout</span>
                  <span className="text-label-sm text-ink-muted">2026 edition</span>
                </div>
              </div>
              <button
                type="button"
                className="focus-ring flex h-11 items-center gap-2.5 rounded-lg border border-border-strong bg-surface-800 px-3 text-body-md text-ink-primary font-semibold hover:bg-surface-700"
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="square"
                  aria-hidden="true"
                >
                  <path d="M10 4v12M4 10h12" />
                </svg>
                <span className="flex-1 text-left">New chat</span>
                <span className="text-label-sm text-ink-muted border border-border-strong px-1.5 rounded">⌘K</span>
              </button>
              <div className="flex-1 min-h-0 overflow-hidden flex flex-col gap-4">
                {/* Today group */}
                <div className="flex flex-col gap-0.5 px-2.5">
                  <span className="text-label-sm px-2.5 pb-1.5">Today</span>
                  <a
                    href="#"
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-lg bg-surface-800 px-2.5 text-body-md text-ink-primary"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="#7E6FEE"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M10 3l6 2.5V10c0 3.5-2.6 6-6 7-3.4-1-6-3.5-6-7V5.5z" />
                    </svg>
                    <span className="flex-1 truncate">Argentina defence</span>
                  </a>
                  <a
                    href="#"
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-lg px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="#95A0B3"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M3 5h14v10H3zM10 5v10" />
                    </svg>
                    <span className="flex-1 truncate">France vs Spain semifinal</span>
                  </a>
                  <a
                    href="#"
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-lg px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="#95A0B3"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M5 16V9M10 16V4M15 16v-5" />
                    </svg>
                    <span className="flex-1 truncate">Messi vs Mbappé</span>
                  </a>
                </div>
                {/* Earlier group */}
                <div className="flex flex-col gap-0.5 px-2.5">
                  <span className="text-label-sm px-2.5 pb-1.5">Earlier</span>
                  <a
                    href="#"
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-lg px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="#95A0B3"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M10 4a3 3 0 1 1 0 6 3 3 0 0 1 0-6M4.5 16.5c0.8-3 3-4.5 5.5-4.5s4.7 1.5 5.5 4.5" />
                    </svg>
                    <span className="flex-1 truncate">Top keepers by saves</span>
                  </a>
                  <a
                    href="#"
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-lg px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="#95A0B3"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M3 5h14v10H3zM10 5v10" />
                    </svg>
                    <span className="flex-1 truncate">Knockout upsets</span>
                  </a>
                  <a
                    href="#"
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-lg px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="#95A0B3"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M10 4a3 3 0 1 1 0 6 3 3 0 0 1 0-6M4.5 16.5c0.8-3 3-4.5 5.5-4.5s4.7 1.5 5.5 4.5" />
                    </svg>
                    <span className="flex-1 truncate">Mbappé tournament</span>
                  </a>
                </div>
              </div>
              {/* Dataset stats */}
              <div className="rounded-xl border border-border-subtle bg-surface-800 p-3.5 shadow-[inset_0_1px_0_rgba(244,246,249,0.04)]">
                <span className="text-label-sm">Dataset</span>
                <div className="grid grid-cols-3 gap-2 mt-2.5">
                  <div className="flex flex-col items-center">
                    <span className="text-data-lg">104</span>
                    <span className="text-label-sm text-ink-muted">matches</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <span className="text-data-lg">48</span>
                    <span className="text-label-sm text-ink-muted">teams</span>
                  </div>
                  <div className="flex flex-col items-center">
                    <span className="text-data-lg">16</span>
                    <span className="text-label-sm text-ink-muted">cities</span>
                  </div>
                </div>
              </div>
              {/* User avatar placeholder */}
              <div className="flex items-center gap-2.5 px-1.5">
                <div className="size-8 rounded-full border border-border-strong bg-surface-700 flex items-center justify-center text-heading-sm">
                  AB
                </div>
                <span className="flex-1 text-body-md text-ink-secondary truncate">Your name</span>
                <button
                  type="button"
                  aria-label="Settings"
                  className="focus-ring size-10 rounded-lg border border-border-strong bg-surface-800 text-ink-secondary hover:bg-surface-700"
                >
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </aside>

        {/* Main content area */}
        <main className="flex min-h-0 min-w-0 grow flex-col">
          {/* Subtle background gradients matching HomeActive.dc.html */}
          <div
            className="absolute inset-0 pointer-events-none"
            aria-hidden="true"
            style={{
              background:
                "radial-gradient(720px 420px at 50% -120px, rgba(126,111,238,0.22), rgba(126,111,238,0) 70%), radial-gradient(520px 360px at 100% 100%, rgba(78,142,247,0.10), rgba(78,142,247,0) 70%)",
            }}
          />
          {/* Decorative SVG grid from HomeActive.dc.html */}
          <svg
            className="absolute inset-0 pointer-events-none"
            width="1176"
            height="900"
            viewBox="0 0 1176 900"
            fill="none"
            stroke="#F4F6F9"
            strokeOpacity="0.035"
            strokeWidth="1.5"
            aria-hidden="true"
            style={{ maxWidth: "100%" }}
          >
            <circle cx="588" cy="520" r="180" />
            <path d="M0 520H1176" />
            <circle cx="588" cy="520" r="4" fill="#F4F6F9" fillOpacity="0.05" />
          </svg>

          {/* Header status badge */}
          <header className="relative z-10 shrink-0 h-16 flex items-center justify-end gap-2 border-b border-border-subtle px-7 md:px-7">
            <span className="focus-ring flex h-8 items-center gap-2 rounded-full border border-border-strong bg-surface-800/70 px-3 text-label-md text-ink-secondary backdrop-blur-sm">
              <span
                className="relative size-1.5 rounded-full bg-data-positive"
                style={{ boxShadow: "0 0 0 3px rgba(53,209,142,0.2)" }}
                aria-hidden="true"
              />
              Tournament data up to date
            </span>
          </header>

          {/* Hero + Composer + Suggested prompts */}
          <div className="relative z-10 flex-1 flex flex-col items-center justify-center gap-8 px-12 pb-14 md:px-12 md:pb-14">
            {/* Hero section */}
            <div className="flex flex-col items-center gap-4 text-center w-full max-w-[760px]">
              {/* "Your World Cup 2026 analyst" badge */}
              <span className="focus-ring flex h-8 items-center gap-2 rounded-full border border-brand/35 bg-brand/12 px-3.5 pl-1.5 text-label-md font-medium">
                <span className="size-5 rounded-full bg-white flex items-center justify-center">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 32 32"
                    aria-hidden="true"
                  >
                    <rect x="7" y="4.5" width="6" height="6" rx="1.6" fill="#4E8EF7" />
                    <rect x="19" y="4.5" width="6" height="6" rx="1.6" fill="#4E8EF7" />
                    <rect x="4" y="9" width="11" height="17.5" rx="5.5" fill="#4E8EF7" />
                    <rect x="17" y="9" width="11" height="17.5" rx="5.5" fill="#4E8EF7" />
                    <rect x="13" y="12" width="6" height="6" rx="1.5" fill="#2F6FD8" />
                    <path
                      d="M16 12.5v5"
                      stroke="#0D0630"
                      strokeOpacity="0.35"
                      strokeWidth="1.2"
                      strokeLinecap="round"
                    />
                    <circle cx="9.5" cy="20.5" r="4" fill="#FFFFFF" stroke="#0D0630" strokeWidth="1.2" />
                    <circle cx="22.5" cy="20.5" r="4" fill="#FFFFFF" stroke="#0D0630" strokeWidth="1.2" />
                    <circle cx="9.5" cy="20.5" r="1.8" fill="#0D0630" />
                    <circle cx="22.5" cy="20.5" r="1.8" fill="#0D0630" />
                    <path
                      d="M20.3 18.6a3 3 0 0 1 1.9-1.1"
                      stroke="#4E8EF7"
                      strokeWidth="1.1"
                      strokeLinecap="round"
                      fill="none"
                    />
                    <circle cx="10.3" cy="19.7" r="0.6" fill="#FFFFFF" />
                    <circle cx="23.3" cy="19.7" r="0.6" fill="#FFFFFF" />
                  </svg>
                </span>
                Your World Cup 2026 analyst
              </span>

              {/* Main headline */}
              <h1 className="text-display-xl md:text-[52px] md:leading-[56px] max-w-[760px] tracking-tight">
                Every match, player and team,
                <br />
                <span className="text-brand-strong">one question away.</span>
              </h1>

              {/* Description */}
              <p className="text-body-lg md:text-body-lg max-w-[560px] text-ink-secondary">
                Ask in plain words. Answers come back as numbers, charts and match breakdowns
                you can open in detail.
              </p>
            </div>

            {/* Composer - larger version for home page */}
            <div className="w-full max-w-[760px]">
              <div className="rounded-2xl border border-border-strong bg-surface-800 shadow-[0_0_0_6px_rgba(126,111,238,0.06),_0_24px_60px_rgba(2,3,5,0.6),_inset_0_1px_0_rgba(244,246,249,0.06)]">
                <label htmlFor="home-composer" className="sr-only">
                  Ask a question
                </label>
                <textarea
                  id="home-composer"
                  rows={2}
                  placeholder="Ask about a team, match or player…"
                  className="h-[72px] w-full rounded-t-2xl px-5.5 pt-5 pb-0 resize-none bg-transparent border-0 text-body-lg text-ink-primary placeholder:text-ink-muted focus:outline-none font-sans"
                />
                <div className="flex items-center gap-2 px-3 py-2.5 pl-4">
                  <button
                    type="button"
                    className="focus-ring flex h-8 items-center gap-1.5 rounded-full border border-border-strong bg-surface-700 px-2.5 text-label-md text-ink-secondary hover:bg-surface-600"
                  >
                    <span className="font-mono text-ink-primary">@</span>
                    Team or player
                  </button>
                  <button
                    type="button"
                    className="focus-ring flex h-8 items-center gap-1.5 rounded-full border border-border-strong bg-surface-700 px-2.5 text-label-md text-ink-secondary hover:bg-surface-600"
                  >
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <rect x="3" y="4" width="14" height="13" />
                      <path d="M3 8h14M7 2v4M13 2v4" />
                    </svg>
                    All stages
                  </button>
                  <div className="flex-1" />
                  <span className="text-body-sm text-ink-muted">
                    <kbd className="font-mono border border-border-strong px-1.5 rounded">⏎</kbd> to send
                  </span>
                  <button
                    type="button"
                    aria-label="Send"
                    className="focus-ring shrink-0 size-10 flex items-center justify-center rounded-xl bg-brand text-on-brand shadow-[0_6px_18px_rgba(126,111,238,0.45),_inset_0_1px_0_rgba(255,255,255,0.25)] hover:shadow-[0_8px_24px_rgba(126,111,238,0.55),_inset_0_1px_0_rgba(255,255,255,0.3)] transition-shadow"
                  >
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M10 16V4M5 9l5-5 5 5" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            {/* Suggested prompts grid */}
            <div className="w-full max-w-[760px] flex flex-col gap-3">
              <span className="text-label-sm text-ink-muted">Try asking</span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {suggestedPrompts.map((prompt) => (
                  <HomePromptCard
                    key={prompt.title}
                    title={prompt.title}
                    hint={prompt.hint}
                    iconPath={prompt.iconPath}
                    tintClass={prompt.tintClass}
                    inkColor={prompt.inkColor}
                    onClick={() => handlePromptClick(prompt.title)}
                  />
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}