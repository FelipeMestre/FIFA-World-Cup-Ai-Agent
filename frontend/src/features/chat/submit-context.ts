/**
 * Optional context forwarded from a composer's selected chip (currently only
 * the Match chip) into `useChatThread`'s `submit`. Carries both the id (sent
 * to the backend so it can resolve the match server-side) and the label
 * (used to build the optimistic user-message `metadata` for instant badge
 * display, before the server echo confirms it).
 */
export interface SubmitContext {
  matchId: number;
  label: string;
}
