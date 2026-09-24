"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { searchRealPlayers } from "@/features/identity-links/api/search-real-players";
import type { RealPlayerSummary } from "@/features/identity-links/types";
import { ApiError } from "@/lib/api/client";

/** Matches the backend's `q: Query(min_length=2)` -- below this, a query
 * would either 422 or (worse, pre-validation) force a near-unfiltered
 * ILIKE scan over every `real_player` row.
 */
const MIN_QUERY_LENGTH = 2;
const SEARCH_DEBOUNCE_MS = 300;
/** Backend caps `limit` at 50; 20 is what this picker actually asks for --
 * one page of realistic candidates, not the whole table.
 */
const RESULT_LIMIT = 20;

/** Search-and-pick dialog backing the "correct match" action: the admin
 * looks up the real Transfermarkt player a doubtful link should actually
 * point to, and confirms it here. Search is live (debounced as the admin
 * types) rather than requiring an explicit submit -- the backend does the
 * actual chunking via SQL LIMIT, so a live query per keystroke never pulls
 * more than `RESULT_LIMIT` rows.
 */
export function CorrectMatchDialog({
  open,
  onOpenChange,
  initialQuery,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialQuery: string;
  onSelect: (realPlayerId: number) => Promise<void>;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<RealPlayerSummary[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectingId, setSelectingId] = useState<number | null>(null);
  const [selectError, setSelectError] = useState<string | null>(null);
  const latestQueryRef = useRef<string>("");

  useEffect(() => {
    if (open) {
      setQuery(initialQuery);
      setResults([]);
      setSearchError(null);
      setSelectError(null);
    }
  }, [open, initialQuery]);

  useEffect(() => {
    if (!open) return;
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setSearchError(null);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const timeoutId = setTimeout(() => {
      latestQueryRef.current = trimmed;
      searchRealPlayers(trimmed, RESULT_LIMIT)
        .then((players) => {
          // A faster later keystroke can resolve after this one -- only
          // apply the response that matches the query still on screen.
          if (latestQueryRef.current !== trimmed) return;
          setResults(players);
          setSearchError(null);
        })
        .catch((caught) => {
          if (latestQueryRef.current !== trimmed) return;
          setSearchError(caught instanceof ApiError ? caught.message : "Search failed");
        })
        .finally(() => {
          if (latestQueryRef.current !== trimmed) return;
          setIsSearching(false);
        });
    }, SEARCH_DEBOUNCE_MS);

    return () => clearTimeout(timeoutId);
  }, [open, query]);

  async function handleSelect(realPlayerId: number) {
    setSelectingId(realPlayerId);
    setSelectError(null);
    try {
      await onSelect(realPlayerId);
      onOpenChange(false);
    } catch (caught) {
      setSelectError(
        caught instanceof ApiError ? caught.message : "Couldn't apply the correct match",
      );
    } finally {
      setSelectingId(null);
    }
  }

  const trimmedQuery = query.trim();
  const belowMinLength = trimmedQuery.length > 0 && trimmedQuery.length < MIN_QUERY_LENGTH;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl sm:max-w-3xl bg-surface-800 text-ink-primary ring-border-strong">
        <DialogHeader>
          <DialogTitle>Correct match</DialogTitle>
          <DialogDescription className="text-ink-secondary">
            Type the player&apos;s Transfermarkt name -- results load automatically.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="real-player-query" className="text-label-md text-ink-secondary">
            Player name
          </Label>
          <Input
            id="real-player-query"
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. Kylian Mbappe"
            className="h-10 border-border-strong bg-surface-900 text-ink-primary"
          />
          {belowMinLength ? (
            <p className="text-label-sm text-ink-muted">
              Keep typing -- at least {MIN_QUERY_LENGTH} characters.
            </p>
          ) : null}
        </div>

        {searchError ? <p className="text-body-sm text-data-negative">{searchError}</p> : null}
        {selectError ? <p className="text-body-sm text-data-negative">{selectError}</p> : null}

        <div className="max-h-96 overflow-auto rounded-lg border border-border-subtle">
          {trimmedQuery.length < MIN_QUERY_LENGTH ? (
            <p className="p-ds-4 text-body-sm text-ink-muted">
              Type a name above to search Transfermarkt players.
            </p>
          ) : isSearching && results.length === 0 ? (
            <p className="p-ds-4 text-body-sm text-ink-muted">Searching…</p>
          ) : results.length === 0 && !searchError ? (
            <p className="p-ds-4 text-body-sm text-ink-muted">
              No players found for &ldquo;{trimmedQuery}&rdquo;.
            </p>
          ) : (
            <table className="w-full min-w-[640px] border-collapse text-left text-body-sm">
              <thead className="sticky top-0 bg-surface-900">
                <tr className="text-label-sm text-ink-muted">
                  <th className="px-ds-3 py-ds-2 font-medium">Name</th>
                  <th className="px-ds-3 py-ds-2 font-medium">Position</th>
                  <th className="px-ds-3 py-ds-2 font-medium">Born</th>
                  <th className="px-ds-3 py-ds-2 font-medium">Nationality</th>
                  <th className="px-ds-3 py-ds-2 font-medium">&nbsp;</th>
                </tr>
              </thead>
              <tbody>
                {results.map((player) => (
                  <tr key={player.playerId} className="border-t border-border-subtle">
                    <td className="px-ds-3 py-ds-2 whitespace-nowrap text-ink-primary">
                      {player.firstName} {player.lastName}
                    </td>
                    <td className="px-ds-3 py-ds-2 whitespace-nowrap text-ink-secondary">
                      {player.position}
                      {player.subPosition ? ` (${player.subPosition})` : ""}
                    </td>
                    <td className="px-ds-3 py-ds-2 whitespace-nowrap text-ink-secondary">
                      {player.dateOfBirth ?? "—"}
                    </td>
                    <td className="px-ds-3 py-ds-2 whitespace-nowrap text-ink-secondary">
                      {player.countryOfCitizenship ?? "—"}
                    </td>
                    <td className="px-ds-3 py-ds-2 text-right">
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={selectingId !== null}
                        onClick={() => handleSelect(player.playerId)}
                        className="border-border-strong whitespace-nowrap text-ink-primary hover:bg-surface-700"
                      >
                        {selectingId === player.playerId ? "Applying…" : "Use this match"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <DialogFooter className="border-border-subtle bg-surface-800">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
