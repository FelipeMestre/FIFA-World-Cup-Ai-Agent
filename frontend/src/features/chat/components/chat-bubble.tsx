import type { ReactNode } from "react";

import { AssistantMark } from "@/components/shared/assistant-mark";

/** The visitor's own message, right-aligned on the violet-tinted user surface. */
export function UserBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[520px] rounded-md bg-chat-user-surface px-4 py-2.5 text-body-lg text-ink-primary">
        {children}
      </div>
    </div>
  );
}

/** The assistant's reply: mark + bubble on surface-800, widgets slot in below. */
export function AssistantBubble({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <AssistantMark size={32} radius="rounded-full" />
      <div className="flex flex-col items-start gap-3">{children}</div>
    </div>
  );
}

export function AssistantText({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-[640px] rounded-md bg-surface-800 px-4 py-3 text-body-lg text-ink-primary">
      {children}
    </div>
  );
}
