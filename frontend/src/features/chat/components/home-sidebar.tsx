import { AssistantMark } from "@/components/shared/assistant-mark";

/**
 * The conversations sidebar (AppSidebar.dc.html): branding, new chat,
 * grouped history, dataset counts and the profile row. Desktop only --
 * the mobile artboards have no sidebar.
 *
 * The history entries and profile are presentational: no threads
 * persistence or account data exists in this build yet.
 */
export function HomeSidebar() {
  return (
        <aside
          className="hidden shrink-0 w-[264px] border-r border-border-subtle bg-surface-900 md:flex md:flex-col"
          aria-label="Conversations"
        >
          <div className="flex min-h-0 grow flex-col gap-5 p-5 pt-6">
              <div className="flex items-center gap-2.5 px-1.5">
                <AssistantMark size={32} radius="rounded-md" />
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
                <div className="flex flex-col gap-0.5 px-2.5">
                  <span className="text-label-sm px-2.5 pb-1.5">Today</span>
                  <a
                    href="#"
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-md bg-surface-800 px-2.5 text-body-md text-ink-primary"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      className="text-brand"
                      stroke="currentColor"
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
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-md px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      className="text-ink-muted"
                      stroke="currentColor"
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
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-md px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      className="text-ink-muted"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="square"
                      aria-hidden="true"
                    >
                      <path d="M5 16V9M10 16V4M15 16v-5" />
                    </svg>
                    <span className="flex-1 truncate">Messi vs Mbappé</span>
                  </a>
                </div>
                <div className="flex flex-col gap-0.5 px-2.5">
                  <span className="text-label-sm px-2.5 pb-1.5">Earlier</span>
                  <a
                    href="#"
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-md px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      className="text-ink-muted"
                      stroke="currentColor"
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
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-md px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      className="text-ink-muted"
                      stroke="currentColor"
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
                    className="focus-ring flex h-10 items-center gap-2.5 rounded-md px-2.5 text-body-md text-ink-secondary hover:bg-surface-800"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 20 20"
                      fill="none"
                      className="text-ink-muted"
                      stroke="currentColor"
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
              <div className="rounded-lg border border-border-subtle bg-surface-800 p-3.5 shadow-[inset_0_1px_0_rgba(244,246,249,0.04)]">
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
        </aside>
  );
}
