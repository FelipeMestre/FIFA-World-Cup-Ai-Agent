import type { ChatMessage } from "@/features/chat/types";

/**
 * Survives a React remount of the chat shell. Next.js App Router can
 * recreate the page/layout tree when `/home` becomes `/home/<uuid>`; the
 * in-flight first turn would otherwise vanish.
 */
const inFlightTurns = new Map<string, ChatMessage[]>();

export function rememberInFlightTurn(conversationId: string, messages: ChatMessage[]): void {
  inFlightTurns.set(conversationId, messages);
}

export function readInFlightTurn(conversationId: string): ChatMessage[] | undefined {
  return inFlightTurns.get(conversationId);
}

export function forgetInFlightTurn(conversationId: string): void {
  inFlightTurns.delete(conversationId);
}

export function clearInFlightTurns(): void {
  inFlightTurns.clear();
}
