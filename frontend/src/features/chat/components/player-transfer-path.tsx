import { transferPathLabel } from "@/features/chat/components/player-club-format";
import type { PlayerTransfer } from "@/features/chat/types";

/** Chronological club moves. Renders nothing when the player has no transfers. */
export function PlayerTransferPath({ transfers }: { transfers: PlayerTransfer[] }) {
  if (transfers.length === 0) {
    return null;
  }

  return (
    <section className="flex shrink-0 flex-col gap-3 p-5">
      <h3 className="text-heading-sm">Transfer path</h3>
      <ol className="flex flex-col gap-2">
        {transfers.map((transfer) => (
          <li
            key={`${transfer.transferDate}-${transfer.fromClub}-${transfer.toClub}`}
            className="text-body-sm text-ink-primary"
          >
            {transferPathLabel(transfer)}
          </li>
        ))}
      </ol>
    </section>
  );
}
