const LINK_ID_PATTERN = /^\d+$/;

/** `player_identity_link.id` is a plain integer primary key, unlike the
 * chat feature's UUID conversation ids.
 */
export function isIdentityLinkId(value: string): boolean {
  return LINK_ID_PATTERN.test(value);
}
