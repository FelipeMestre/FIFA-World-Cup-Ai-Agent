import Link from "next/link";
import { Loader2, LogOut, Pencil } from "lucide-react";

import { AssistantMark } from "@/components/shared/assistant-mark";
import { initialsFromName } from "@/features/auth/initials";
import { groupConversations } from "@/features/chat/group-conversations";
import type { ConversationSummary } from "@/features/chat/types";

function ConversationRow({
  conversation,
  isActive,
  onRename,
}: {
  conversation: ConversationSummary;
  isActive: boolean;
  onRename: (conversation: ConversationSummary) => void;
}) {
  return (
    <div
      className={
        isActive
          ? "group flex h-10 items-center gap-0.5 rounded-md bg-surface-800 pr-1"
          : "group flex h-10 items-center gap-0.5 rounded-md pr-1 hover:bg-surface-800"
      }
    >
      <Link
        href={`/home/${conversation.id}`}
        className={
          isActive
            ? "focus-ring flex min-w-0 flex-1 items-center gap-2.5 rounded-md px-2.5 text-body-md text-ink-primary"
            : "focus-ring flex min-w-0 flex-1 items-center gap-2.5 rounded-md px-2.5 text-body-md text-ink-secondary"
        }
      >
        {conversation.isGenerating ? (
          <Loader2
            className={isActive ? "size-4 shrink-0 animate-spin text-brand" : "size-4 shrink-0 animate-spin text-ink-muted"}
            aria-hidden="true"
          />
        ) : (
          <svg
            width="16"
            height="16"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            className={isActive ? "text-brand" : "text-ink-muted"}
            strokeWidth="1.5"
            strokeLinecap="square"
            aria-hidden="true"
          >
            <path d="M3 4h14v10H8l-3 3v-3H3z" />
          </svg>
        )}
        <span className="flex-1 truncate">{conversation.title || "New chat"}</span>
        {conversation.isGenerating ? (
          <span className="sr-only">Generating a reply</span>
        ) : null}
      </Link>
      <button
        type="button"
        aria-label={`Rename ${conversation.title || "chat"}`}
        onClick={() => onRename(conversation)}
        className="hover:cursor-pointer focus-ring flex size-8 shrink-0 items-center justify-center rounded-md text-ink-muted opacity-0 hover:bg-surface-700 hover:text-ink-primary group-hover:opacity-100 group-focus-within:opacity-100"
      >
        <Pencil className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}

function ConversationGroup({
  label,
  conversations,
  activeId,
  onRename,
}: {
  label: string;
  conversations: ConversationSummary[];
  activeId: string | null;
  onRename: (conversation: ConversationSummary) => void;
}) {
  if (conversations.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-0.5 px-2.5">
      <span className="px-2.5 pb-1.5 text-label-sm">{label}</span>
      {conversations.map((conversation) => (
        <ConversationRow
          key={conversation.id}
          conversation={conversation}
          isActive={conversation.id === activeId}
          onRename={onRename}
          className="hover:cursor-pointer"
        />
      ))}
    </div>
  );
}

/**
 * The conversations sidebar (AppSidebar.dc.html): branding, new chat,
 * grouped history, dataset counts and the profile row. Desktop only --
 * the mobile artboards have no sidebar.
 */
export function HomeSidebar({
  conversations,
  activeId,
  isLoading,
  loadError,
  userName,
  onNewChat,
  onRename,
  onLogout,
}: {
  conversations: ConversationSummary[];
  activeId: string | null;
  isLoading: boolean;
  loadError: string | null;
  userName: string;
  onNewChat?: () => void;
  onRename: (conversation: ConversationSummary) => void;
  onLogout: () => void;
}) {
  const grouped = groupConversations(conversations);
  const isEmpty = !isLoading && conversations.length === 0 && loadError === null;
  const initials = initialsFromName(userName);

  return (
        <aside
          className="hidden w-[264px] shrink-0 border-r border-border-subtle bg-surface-900 md:flex md:flex-col"
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
                onClick={onNewChat}
                className="focus-ring flex h-11 items-center gap-2.5 rounded-lg border border-border-strong bg-surface-800 px-3 text-body-md font-semibold text-ink-primary hover:bg-surface-700 hover:cursor-pointer"
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
                <span className="rounded border border-border-strong px-1.5 text-label-sm text-ink-muted">⌘K</span>
              </button>
              <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto">
                {isLoading && (
                  <p className="px-5 text-label-sm text-ink-muted">Loading conversations…</p>
                )}
                {loadError && (
                  <p className="px-5 text-label-sm text-ink-muted">{loadError}</p>
                )}
                {isEmpty && (
                  <p className="px-5 text-label-sm text-ink-muted">No conversations yet</p>
                )}
                <ConversationGroup
                  label="Today"
                  conversations={grouped.today}
                  activeId={activeId}
                  onRename={onRename}
                />
                <ConversationGroup
                  label="Earlier"
                  conversations={grouped.earlier}
                  activeId={activeId}
                  onRename={onRename}
                />
              </div>
              <div className="rounded-lg border border-border-subtle bg-surface-800 p-3.5 shadow-[inset_0_1px_0_rgba(244,246,249,0.04)]">
                <span className="text-label-sm">Dataset</span>
                <div className="mt-2.5 grid grid-cols-3 gap-2">
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
                <div className="flex size-8 items-center justify-center rounded-full border border-border-strong bg-surface-700 text-heading-sm">
                  {initials}
                </div>
                <span className="flex-1 truncate text-body-md text-ink-secondary">{userName}</span>
                <button
                  type="button"
                  aria-label="Log out"
                  onClick={onLogout}
                  className="focus-ring size-10 rounded-lg border border-border-strong bg-surface-800 text-ink-secondary hover:bg-surface-700 hover:cursor-pointer"
                >
                  <LogOut className="mx-auto size-[18px]" aria-hidden="true" />
                </button>
              </div>
          </div>
        </aside>
  );
}
