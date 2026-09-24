/** Shared by the review card and the correct-match dialog, both of which
 * display a player's market value.
 */
export function formatEur(value: number | null): string {
  if (value === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}
