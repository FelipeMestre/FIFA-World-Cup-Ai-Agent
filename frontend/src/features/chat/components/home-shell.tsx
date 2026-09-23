"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useParams, useRouter } from "next/navigation";

import { AppHeader } from "@/components/layout/app-header";
import { HomePromptCard } from "@/features/chat/components/home-prompt-card";
import { HomeSidebar } from "@/features/chat/components/home-sidebar";
import { HomeThread } from "@/features/chat/components/home-thread";
import { RenameConversationDialog } from "@/features/chat/components/rename-conversation-dialog";
import { SidePanel } from "@/features/chat/components/side-panel";
import { ThreadComposer } from "@/features/chat/components/thread-composer";
import { ThreadHeader } from "@/features/chat/components/thread-header";
import { isConversationId } from "@/features/chat/conversation-id";
import { ThreadHydrationProvider } from "@/features/chat/thread-hydration-context";
import { useChatPanel } from "@/features/chat/hooks/use-chat-panel";
import { useChatThread } from "@/features/chat/hooks/use-chat-thread";
import { useConversationList } from "@/features/chat/hooks/use-conversation-list";
import type { ConversationSummary } from "@/features/chat/types";
import { useMediaQuery } from "@/hooks/use-media-query";

function conversationIdFromParams(raw: string | string[] | undefined): string | null {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return typeof value === "string" && isConversationId(value) ? value : null;
}

const MOBILE_BREAKPOINT = "(max-width: 767px)";

/**
 * Home page shell (HomeActive.dc.html + MobileEmpty.dc.html).
 * Desktop: sidebar + hero + composer + 2x2 prompt grid
 * Mobile: no sidebar, stacked full-width prompt buttons, bottom composer
 */
export function HomeShell({ children }: { children?: ReactNode }) {
  const router = useRouter();
  const params = useParams();
  const urlConversationId = conversationIdFromParams(
    params.conversationId as string | string[] | undefined,
  );
  const isMobile = useMediaQuery(MOBILE_BREAKPOINT);
  const [draft, setDraft] = useState("");
  const {
    messages,
    conversationId,
    isSending,
    isLoadingHistory,
    submit,
    reset,
    resolveEntity,
    hydrate,
  } = useChatThread({
    urlConversationId,
    onConversationCreated: (id) => {
      // Native history so Next does not remount the home layout on first send.
      window.history.replaceState(window.history.state, "", `/home/${id}`);
    },
  });
  const panel = useChatPanel();
  const conversationList = useConversationList();
  const refreshConversations = conversationList.refresh;
  const wasSending = useRef(false);
  const [renameTarget, setRenameTarget] = useState<ConversationSummary | null>(null);

  useEffect(() => {
    if (wasSending.current && !isSending) {
      void refreshConversations();
    }
    wasSending.current = isSending;
  }, [isSending, refreshConversations]);

  const hasThread = messages.length > 0 || Boolean(conversationId) || isLoadingHistory;
  const listedTitle = conversationList.conversations.find((row) => row.id === conversationId)?.title;
  const firstQuestion = messages.find((message) => message.role === "user");
  const firstQuestionTitle =
    firstQuestion?.parts[0]?.type === "text" ? firstQuestion.parts[0].content : null;
  const threadTitle = listedTitle || firstQuestionTitle || "New chat";

  const panelSourcePreview = (() => {
    const source = messages.find((message) => message.id === panel.state.sourceMessageId);
    const part = source?.parts[0];
    return part?.type === "text" ? part.content : "";
  })();

  // Suggested prompts matching HomeActive.dc.html / MobileEmpty.dc.html
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

  /** Opens the thread in place -- the thread is a state of this page. */
  const startChat = (message: string) => {
    const trimmed = message.trim();
    if (!trimmed || isSending) return;
    submit(trimmed);
    setDraft("");
  };

  const startNewChat = () => {
    panel.close();
    reset();
    window.history.replaceState(window.history.state, "", "/home");
    if (urlConversationId) {
      router.push("/home");
    }
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      startChat(draft);
    }
  };

  return (
    <ThreadHydrationProvider value={hydrate}>
      <div className="flex h-dvh flex-col bg-surface-950">
        {/* The desktop artboards have no global top bar -- branding lives in
            the sidebar, and the content column owns its own header. Only the
            mobile artboards have one. */}
        <div className="shrink-0 md:hidden">
          <AppHeader />
        </div>
        <div className="flex min-h-0 grow">
          <HomeSidebar
            conversations={conversationList.conversations}
            activeId={conversationId}
            isLoading={conversationList.isLoading}
            loadError={conversationList.loadError}
            onNewChat={startNewChat}
            onRename={setRenameTarget}
          />

          {/* ThreadHeader spans this column (main + side panel) so the panel
              starts right where it ends, with no gap and no header of its own
              duplicating it -- see ThreadHeader's docstring. */}
          <div className="flex min-h-0 grow flex-col">
            {hasThread && (
              <ThreadHeader
                title={threadTitle}
                messages={messages}
                canRename={Boolean(conversationId)}
                onRename={() => {
                  if (!conversationId) return;
                  setRenameTarget({
                    id: conversationId,
                    title: threadTitle,
                    updatedAt: new Date().toISOString(),
                    createdAt: new Date().toISOString(),
                  });
                }}
              />
            )}
            <div className="flex min-h-0 grow">
              {/* Main content area */}
              <main className="relative flex min-h-0 min-w-0 grow flex-col">
                {/* Background gradients - desktop only (the mobile artboards are a
                    solid surface). The thread state dims the wash and drops the
                    pitch markings so they don't compete with the answers. */}
                {!isMobile && (
                  <>
                    <div
                      className="absolute inset-0 pointer-events-none"
                      aria-hidden="true"
                      style={{
                        background: hasThread
                          ? "radial-gradient(720px 420px at 50% -160px, rgba(126,111,238,0.16), rgba(126,111,238,0) 70%)"
                          : "radial-gradient(720px 420px at 50% -120px, rgba(126,111,238,0.22), rgba(126,111,238,0) 70%), radial-gradient(520px 360px at 100% 100%, rgba(78,142,247,0.10), rgba(78,142,247,0) 70%)",
                      }}
                    />
                    {!hasThread && (
                      <svg
                        className="absolute inset-0 size-full pointer-events-none"
                        viewBox="0 0 1176 900"
                        preserveAspectRatio="xMidYMid slice"
                        fill="none"
                        stroke="#F4F6F9"
                        strokeOpacity="0.035"
                        strokeWidth="1.5"
                        aria-hidden="true"
                      >
                        <circle cx="588" cy="520" r="180" />
                        <path d="M0 520H1176" />
                        <circle cx="588" cy="520" r="4" fill="#F4F6F9" fillOpacity="0.05" />
                      </svg>
                    )}
                  </>
                )}

                {/* Header status badge - empty state only; the thread brings its own. */}
                {!isMobile && !hasThread && (
                  <header className="relative z-10 shrink-0 h-16 flex items-center justify-end gap-2 border-b border-border-subtle px-7">
                    <span className="focus-ring flex h-8 items-center gap-2 rounded-full border border-border-strong bg-surface-800/70 px-3 text-label-md text-ink-secondary backdrop-blur-sm">
                      <span
                        className="relative size-1.5 rounded-full bg-data-positive"
                        style={{ boxShadow: "0 0 0 3px rgba(53,209,142,0.2)" }}
                        aria-hidden="true"
                      />
                      Tournament data up to date
                    </span>
                  </header>
                )}

                {/* Hero + Prompts + Composer. Scrolls inside the shell rather than
                    scrolling the page, so the header and sidebar stay put on short
                    viewports. */}
                <div className="relative z-10 flex min-h-0 flex-1 flex-col overflow-y-auto">
                  {hasThread && (
                    <HomeThread
                      messages={messages}
                      openEntity={panel.state.openEntity}
                      onOpenEntity={panel.openEntity}
                      onRegenerate={submit}
                    >
                      {children}
                    </HomeThread>
                  )}

                  {/* Desktop: centered hero + composer + 2x2 grid */}
                  {!hasThread && !isMobile && (
                    <div className="flex-1 flex flex-col items-center justify-center-safe gap-8 px-12 pb-14">
                      {/* Hero section */}
                      <div className="flex flex-col items-center gap-4 text-center w-full max-w-[760px]">
                        <span className="focus-ring flex h-8 items-center gap-2 rounded-full border border-brand/35 bg-brand/12 px-3.5 pl-1.5 text-label-md font-medium">
                          <span className="size-5 rounded-full bg-white flex items-center justify-center">
                            <svg width="16" height="16" viewBox="0 0 32 32" aria-hidden="true">
                              <rect x="7" y="4.5" width="6" height="6" rx="1.6" fill="#4E8EF7" />
                              <rect x="19" y="4.5" width="6" height="6" rx="1.6" fill="#4E8EF7" />
                              <rect x="4" y="9" width="11" height="17.5" rx="5.5" fill="#4E8EF7" />
                              <rect x="17" y="9" width="11" height="17.5" rx="5.5" fill="#4E8EF7" />
                              <rect x="13" y="12" width="6" height="6" rx="1.5" fill="#2F6FD8" />
                              <path d="M16 12.5v5" stroke="#0D0630" strokeOpacity="0.35" strokeWidth="1.2" strokeLinecap="round" />
                              <circle cx="9.5" cy="20.5" r="4" fill="#FFFFFF" stroke="#0D0630" strokeWidth="1.2" />
                              <circle cx="22.5" cy="20.5" r="4" fill="#FFFFFF" stroke="#0D0630" strokeWidth="1.2" />
                              <circle cx="9.5" cy="20.5" r="1.8" fill="#0D0630" />
                              <circle cx="22.5" cy="20.5" r="1.8" fill="#0D0630" />
                              <path d="M20.3 18.6a3 3 0 0 1 1.9-1.1" stroke="#4E8EF7" strokeWidth="1.1" strokeLinecap="round" fill="none" />
                              <circle cx="10.3" cy="19.7" r="0.6" fill="#FFFFFF" />
                              <circle cx="23.3" cy="19.7" r="0.6" fill="#FFFFFF" />
                            </svg>
                          </span>
                          Your World Cup 2026 analyst
                        </span>
                        <h1 className="text-display-xl md:text-[52px] md:leading-[56px] max-w-[760px] tracking-tight">
                          Every match, player and team,
                          <br />
                          <span className="text-brand-strong">one question away.</span>
                        </h1>
                        <p className="text-body-lg max-w-[560px] text-ink-secondary">
                          Ask in plain words. Answers come back as numbers, charts and match breakdowns
                          you can open in detail.
                        </p>
                      </div>

                      {/* Desktop Composer - larger with chips */}
                      <div className="w-full max-w-[760px]">
                        <div className="rounded-2xl border border-border-strong bg-surface-800 shadow-[0_0_0_6px_rgba(126,111,238,0.06),_0_24px_60px_rgba(2,3,5,0.6),_inset_0_1px_0_rgba(244,246,249,0.06)]">
                          <label htmlFor="home-composer" className="sr-only">Ask a question</label>
                          <textarea
                            id="home-composer"
                            rows={2}
                            value={draft}
                            onChange={(event) => setDraft(event.target.value)}
                            onKeyDown={handleComposerKeyDown}
                            placeholder="Ask about a team, match or player…"
                            className="h-[72px] w-full rounded-t-2xl px-5.5 pt-5 pb-0 resize-none bg-transparent border-0 text-body-lg text-ink-primary placeholder:text-ink-muted focus:outline-none font-sans"
                          />
                          <div className="flex items-center gap-2 px-3 py-2.5 pl-4">
                            <button type="button" className="focus-ring flex h-8 items-center gap-1.5 rounded-full border border-border-strong bg-surface-700 px-2.5 text-label-md text-ink-secondary hover:bg-surface-600">
                              <span className="font-mono text-ink-primary">@</span> Team or player
                            </button>
                            <button type="button" className="focus-ring flex h-8 items-center gap-1.5 rounded-full border border-border-strong bg-surface-700 px-2.5 text-label-md text-ink-secondary hover:bg-surface-600">
                              <svg width="14" height="14" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" aria-hidden="true">
                                <rect x="3" y="4" width="14" height="13" />
                                <path d="M3 8h14M7 2v4M13 2v4" />
                              </svg> All stages
                            </button>
                            <div className="flex-1" />
                            <span className="text-body-sm text-ink-muted"><kbd className="font-mono border border-border-strong px-1.5 rounded">⏎</kbd> to send</span>
                            <button type="button" aria-label="Send" onClick={() => startChat(draft)} disabled={draft.trim().length === 0} className="focus-ring shrink-0 size-10 flex items-center justify-center rounded-xl bg-brand text-on-brand shadow-[0_6px_18px_rgba(126,111,238,0.45),_inset_0_1px_0_rgba(255,255,255,0.25)] hover:shadow-[0_8px_24px_rgba(126,111,238,0.55),_inset_0_1px_0_rgba(255,255,255,0.3)] transition-shadow disabled:opacity-40">
                              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square" aria-hidden="true"><path d="M10 16V4M5 9l5-5 5 5" /></svg>
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Desktop 2x2 prompt grid */}
                      <div className="w-full max-w-[760px] flex flex-col gap-3">
                        <span className="text-label-sm text-ink-muted">Try asking</span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                          {suggestedPrompts.map((prompt) => (
                            <HomePromptCard key={prompt.title} {...prompt} onClick={() => startChat(prompt.title)} />
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Mobile: stacked layout matching MobileEmpty.dc.html */}
                  {!hasThread && isMobile && (
                    <div className="flex-1 flex flex-col justify-end gap-6 px-4 pb-6">
                      {/* Mobile Hero */}
                      <div className="flex flex-col items-center gap-2 text-center">
                        <span className="text-label-sm text-ink-muted">World Cup 2026 · 104 matches</span>
                        <h1 className="text-heading-md">Ask anything about the tournament</h1>
                        <p className="text-body-sm text-ink-secondary max-w-[300px]">Teams, matches and players, answered with tournament data.</p>
                      </div>

                      {/* Mobile Prompts - full-width stacked buttons */}
                      <div className="flex flex-col gap-2">
                        {suggestedPrompts.map((prompt) => (
                          <button
                            key={prompt.title}
                            type="button"
                            onClick={() => startChat(prompt.title)}
                            className="focus-ring min-h-[48px] flex items-center gap-3 rounded-lg border border-border-strong bg-surface-900 px-4 text-left text-body-md text-ink-primary hover:bg-surface-800"
                          >
                            <svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke={prompt.inkColor} strokeWidth="1.5" strokeLinecap="square" aria-hidden="true">
                              <path d={prompt.iconPath} />
                            </svg>
                            <span className="truncate">{prompt.title}</span>
                          </button>
                        ))}
                      </div>

                      {/* Mobile Composer - fixed bottom */}
                      <div className="shrink-0">
                        <div className="flex items-center gap-2 rounded-full border border-border-strong bg-surface-700 py-1.5 pl-4 pr-1.5">
                          <label htmlFor="home-composer-mobile" className="sr-only">Ask a question</label>
                          <textarea
                            id="home-composer-mobile"
                            rows={1}
                            value={draft}
                            onChange={(event) => setDraft(event.target.value)}
                            onKeyDown={handleComposerKeyDown}
                            placeholder="Ask about a team, match or player…"
                            className="h-11 flex-1 resize-none bg-transparent border-0 text-body-lg text-ink-primary placeholder:text-ink-muted focus:outline-none font-sans"
                          />
                          <button
                            type="button"
                            aria-label="Send"
                            onClick={() => startChat(draft)}
                            disabled={draft.trim().length === 0}
                            className="focus-ring shrink-0 size-11 flex items-center justify-center rounded-full bg-brand text-on-brand disabled:opacity-40"
                          >
                            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="square" aria-hidden="true">
                              <path d="M4 10h12M11 5l5 5-5 5" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {hasThread && <ThreadComposer isSending={isSending} onSubmit={submit} />}
              </main>

              <SidePanel
                panelState={panel.state}
                resolveEntity={resolveEntity}
                fromMessagePreview={panelSourcePreview}
                onCollapse={panel.collapse}
                onExpand={panel.expand}
                onClose={panel.close}
                onJumpToMessage={panel.jumpToMessage}
              />
            </div>
          </div>
        </div>
        <RenameConversationDialog
          conversationId={renameTarget?.id ?? null}
          currentTitle={renameTarget?.title ?? ""}
          open={renameTarget !== null}
          onOpenChange={(open) => {
            if (!open) setRenameTarget(null);
          }}
          onSave={conversationList.rename}
        />
      </div>
    </ThreadHydrationProvider>
  );
}
