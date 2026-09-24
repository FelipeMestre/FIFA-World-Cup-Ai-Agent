import Link from "next/link";

import { AssistantMark } from "@/components/shared/assistant-mark";
import { Button } from "@/components/ui/button";

/** Top bar for `(admin)` routes -- distinct from the chat `AppHeader`
 * (no History/New chat actions, which don't apply here), but matching its
 * visual language (same brand mark, 64px desktop height, surface-900 bar).
 */
export function AdminHeader({ userName }: { userName: string }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-ds-3 border-b border-border-subtle bg-surface-900 px-ds-4 md:h-16 md:px-ds-6">
      <AssistantMark size={28} className="md:hidden" />
      <AssistantMark size={32} className="hidden md:flex" />
      <span className="truncate text-heading-sm md:text-heading-md">Owl Analytics</span>
      <span className="hidden h-[22px] items-center rounded-sm border border-border-strong px-ds-2 text-label-sm text-ink-secondary md:flex">
        Admin
      </span>
      <div className="grow" />
      <span className="hidden text-body-sm text-ink-secondary md:inline">{userName}</span>
      <Button
        type="button"
        variant="outline"
        className="border-border-strong bg-transparent text-ink-primary hover:bg-surface-700"
        nativeButton={false}
        render={<Link href="/home" />}
      >
        Back to chat
      </Button>
    </header>
  );
}
