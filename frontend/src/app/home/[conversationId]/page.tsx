import { Suspense } from "react";
import { notFound, redirect } from "next/navigation";

import { ConversationHydrator } from "@/features/chat/components/conversation-hydrator";
import { MessageListSkeleton } from "@/features/chat/components/message-list-skeleton";
import { isConversationId } from "@/features/chat/conversation-id";
import { parseConversationReplay } from "@/features/chat/api/get-conversation-messages";
import { proxyBackendJson } from "@/lib/api/proxy-backend-json";

/**
 * `/home/<uuid>` — server-fetches the conversation's full history (never
 * Redis, per the backend's own design: Redis only caches flat role+content
 * for the LLM prompt path, not the widget-bearing UI shape) so the first
 * paint already has the latest data. 404/not-owned (the backend collapses
 * both into one 404) becomes Next's notFound(), not a silent client swallow.
 */
export default function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  return (
    <Suspense fallback={<MessageListSkeleton />}>
      <ConversationContent params={params} />
    </Suspense>
  );
}

async function ConversationContent({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  if (!isConversationId(conversationId)) {
    redirect("/home");
  }

  const response = await proxyBackendJson(`/conversations/${conversationId}/messages`);
  if (response.status === 404) {
    notFound();
  }
  if (!response.ok) {
    // Transient/network failure -- don't hard-fail the page; the client's
    // own history-load effect in useChatThread will retry this fetch since
    // hydratedConversationIdRef never gets set for this conversation.
    return null;
  }

  const replay = parseConversationReplay(await response.json());
  return <ConversationHydrator conversationId={conversationId} replay={replay} />;
}
