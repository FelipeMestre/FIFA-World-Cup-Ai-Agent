import {
  formatTransferFee,
  formatTransferMonth,
  formatTransferValue,
} from "@/features/chat/components/player-club-format";
import type { PlayerTransfer } from "@/features/chat/types";

const HEADER_CELL =
  "sticky top-0 z-10 border-b border-border-strong bg-surface-800 text-label-sm text-ink-muted";
const BODY_CELL = "border-b border-border-subtle bg-surface-800 text-body-sm text-ink-secondary";

/** Chronological club moves. Renders nothing when the player has no transfers. */
export function PlayerTransferPath({ transfers }: { transfers: PlayerTransfer[] }) {
  if (transfers.length === 0) {
    return null;
  }

  return (
    <section className="flex shrink-0 flex-col gap-3 border-b border-border-subtle p-5">
      <h3 className="text-heading-sm">Transfer path</h3>
      <div className="max-h-96 overflow-auto rounded-lg border border-border-strong">
        <table className="w-full border-separate border-spacing-0 bg-surface-800">
          <thead>
            <tr className="h-9">
              <th scope="col" className={`${HEADER_CELL} px-3 text-left`}>
                Date
              </th>
              <th scope="col" className={`${HEADER_CELL} px-2 text-left`}>
                From
              </th>
              <th scope="col" className={`${HEADER_CELL} px-2 text-left`}>
                To
              </th>
              <th scope="col" className={`${HEADER_CELL} px-2 text-right`}>
                Fee
              </th>
              <th scope="col" className={`${HEADER_CELL} pr-3 pl-2 text-right`}>
                Value
              </th>
            </tr>
          </thead>
          <tbody>
            {transfers.map((transfer) => (
              <tr
                key={`${transfer.transferDate}-${transfer.fromClub}-${transfer.toClub}`}
                className="h-10"
              >
                <th
                  scope="row"
                  className={`${BODY_CELL} px-3 text-left font-normal whitespace-nowrap text-ink-primary`}
                >
                  {formatTransferMonth(transfer.transferDate)}
                </th>
                <td className={`${BODY_CELL} max-w-40 truncate px-2 text-left`} title={transfer.fromClub}>
                  {transfer.fromClub}
                </td>
                <td className={`${BODY_CELL} max-w-40 truncate px-2 text-left`} title={transfer.toClub}>
                  {transfer.toClub}
                </td>
                <td className={`${BODY_CELL} px-2 text-right whitespace-nowrap`}>
                  {formatTransferFee(transfer.feeEur)}
                </td>
                <td className={`${BODY_CELL} pr-3 pl-2 text-right whitespace-nowrap`}>
                  {formatTransferValue(transfer.marketValueEur)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
