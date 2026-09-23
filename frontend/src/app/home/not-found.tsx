import Link from "next/link";

/**
 * `/home/<uuid>` where the conversation is missing or not owned by the
 * signed-in user -- the backend collapses both cases into one 404.
 */
export default function ConversationNotFound() {
  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-ds-4 bg-surface-950 px-ds-6 text-center">
      <h1 className="text-heading-md text-ink-primary">Conversation not found</h1>
      <p className="max-w-[420px] text-body-md text-ink-secondary">
        This conversation doesn&apos;t exist, or you don&apos;t have access to it.
      </p>
      <Link
        href="/home"
        className="focus-ring rounded-full border border-border-strong bg-surface-800 px-ds-4 py-ds-2 text-label-md text-ink-primary hover:bg-surface-700"
      >
        Back to chat
      </Link>
    </div>
  );
}
