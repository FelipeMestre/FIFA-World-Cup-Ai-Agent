"use client";

import { useEffect, useState, type FormEvent } from "react";

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

/** Search-and-pick dialog backing the "correct match" action: the admin
 * looks up the real Transfermarkt player a doubtful link should actually
 * point to, and confirms it here.
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

  useEffect(() => {
    if (open) {
      setQuery(initialQuery);
      setResults([]);
      setSearchError(null);
      setSelectError(null);
    }
  }, [open, initialQuery]);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setIsSearching(true);
    setSearchError(null);
    try {
      setResults(await searchRealPlayers(trimmed));
    } catch (caught) {
      setSearchError(caught instanceof ApiError ? caught.message : "Search failed");
    } finally {
      setIsSearching(false);
    }
  }

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg bg-surface-800 text-ink-primary ring-border-strong">
        <DialogHeader>
          <DialogTitle>Correct match</DialogTitle>
          <DialogDescription className="text-ink-secondary">
            Search Transfermarkt for the real player this roster entry should link to.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSearch} className="flex items-end gap-ds-2">
          <div className="flex grow flex-col gap-1.5">
            <Label htmlFor="real-player-query" className="text-label-md text-ink-secondary">
              Player name
            </Label>
            <Input
              id="real-player-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="e.g. Kylian Mbappe"
              className="h-10 border-border-strong bg-surface-900 text-ink-primary"
            />
          </div>
          <Button type="submit" disabled={isSearching || !query.trim()}>
            {isSearching ? "Searching…" : "Search"}
          </Button>
        </form>

        {searchError ? <p className="text-body-sm text-data-negative">{searchError}</p> : null}
        {selectError ? <p className="text-body-sm text-data-negative">{selectError}</p> : null}

        <div className="flex max-h-80 flex-col gap-ds-2 overflow-y-auto">
          {results.length === 0 && !isSearching && !searchError ? (
            <p className="text-body-sm text-ink-muted">
              {query.trim() ? "No matches yet -- try Search." : "Type a name and search."}
            </p>
          ) : null}
          {results.map((player) => (
            <div
              key={player.playerId}
              className="flex items-center justify-between gap-ds-3 rounded-lg border border-border-subtle bg-surface-900 p-ds-3"
            >
              <div className="flex flex-col">
                <span className="text-body-md text-ink-primary">
                  {player.firstName} {player.lastName}
                </span>
                <span className="text-body-sm text-ink-muted">
                  {player.position}
                  {player.dateOfBirth ? ` · b. ${player.dateOfBirth}` : ""}
                  {player.countryOfCitizenship ? ` · ${player.countryOfCitizenship}` : ""}
                </span>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={selectingId !== null}
                onClick={() => handleSelect(player.playerId)}
                className="border-border-strong text-ink-primary hover:bg-surface-700"
              >
                {selectingId === player.playerId ? "Applying…" : "Use this match"}
              </Button>
            </div>
          ))}
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
